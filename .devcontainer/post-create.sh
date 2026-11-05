#!/usr/bin/env bash
# Runs once after the container is created: installs the pinned CLIs (Claude Code, kmcp, kagent;
# kmcp and kagent into /usr/local/bin via sudo), syncs Python deps if there is a project, prints versions.
set -euo pipefail

CLAUDE_CODE_VERSION=2.1.316
KMCP_VERSION=v0.4.0
KAGENT_VERSION=v0.10.4
VHS_VERSION=v0.12.1   # charmbracelet/vhs: renders the before clip (media/before-clip.tape)
TTYD_VERSION=1.7.7    # VHS needs ttyd >= 1.7.2; Debian 12 has no package
GO_VERSION=1.26.10   # only to build the kagent CLI: the v0.10.4 release has no CLI binaries
ARCH="$(dpkg --print-architecture)"   # amd64 | arm64

if ! claude --version 2>/dev/null | grep -q "^${CLAUDE_CODE_VERSION} "; then
  echo "== Installing Claude Code ${CLAUDE_CODE_VERSION}"
  npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}"
fi

if ! kmcp --version 2>/dev/null | grep -q "${KMCP_VERSION#v}"; then
  echo "== Installing kmcp CLI ${KMCP_VERSION}"
  tmp="$(mktemp -d)"
  url="https://github.com/kagent-dev/kmcp/releases/download/${KMCP_VERSION}/kmcp-linux-${ARCH}"
  curl -fsSL -o "$tmp/kmcp" "$url"
  [ "$(sha256sum "$tmp/kmcp" | cut -d' ' -f1)" = "$(curl -fsSL "$url.sha256" | cut -d' ' -f1)" ] \
    || { echo "kmcp checksum mismatch" >&2; exit 1; }
  sudo install -m 0755 "$tmp/kmcp" /usr/local/bin/kmcp
  rm -rf "$tmp"
fi

# kagent CLI: built from the v0.10.4 tag (the release workflow skipped the binaries) with the
# Makefile's version ldflags. Never `get-kagent` (installs latest = 1.0 RC) and never `kagent install`.
if ! kagent version 2>/dev/null | grep -q "${KAGENT_VERSION}"; then
  echo "== Building kagent CLI ${KAGENT_VERSION} (temporary Go ${GO_VERSION})"
  tmp="$(mktemp -d)"
  curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-${ARCH}.tar.gz" | tar -xz -C "$tmp"
  git clone --quiet --depth 1 --branch "$KAGENT_VERSION" https://github.com/kagent-dev/kagent.git "$tmp/src"
  pkg=github.com/kagent-dev/kagent/go/core/internal/version
  ldflags="-X $pkg.Version=${KAGENT_VERSION} -X $pkg.GitCommit=$(git -C "$tmp/src" rev-parse --short HEAD) -X $pkg.BuildDate=$(date -u +%Y-%m-%d)"
  (cd "$tmp/src/go" && GOPATH="$tmp/gopath" GOCACHE="$tmp/cache" GOTOOLCHAIN=local CGO_ENABLED=0 \
    "$tmp/go/bin/go" build -ldflags "$ldflags" -o "$tmp/kagent" ./core/cli/cmd/kagent)
  sudo install -m 0755 "$tmp/kagent" /usr/local/bin/kagent
  chmod -R u+w "$tmp" && rm -rf "$tmp"   # the Go module cache is read-only
fi

# The before clip: VHS drives ttyd in headless Chromium and encodes with ffmpeg. JetBrains Mono
# for the text, Symbola for Claude Code's mode icons. Both binaries checked against the release checksums.
if ! vhs --version 2>/dev/null | grep -q "${VHS_VERSION}"; then
  echo "== Installing VHS ${VHS_VERSION}, ttyd ${TTYD_VERSION}, ffmpeg, Chromium, fonts"
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
    ffmpeg chromium fonts-jetbrains-mono fonts-symbola >/dev/null
  tmp="$(mktemp -d)"
  ttyd_arch="$([ "$ARCH" = arm64 ] && echo aarch64 || echo x86_64)"
  ttyd_url="https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}"
  curl -fsSL -o "$tmp/ttyd.$ttyd_arch" "$ttyd_url/ttyd.$ttyd_arch"
  curl -fsSL "$ttyd_url/SHA256SUMS" | grep " ttyd.$ttyd_arch\$" | (cd "$tmp" && sha256sum -c -) >/dev/null
  sudo install -m 0755 "$tmp/ttyd.$ttyd_arch" /usr/local/bin/ttyd
  vhs_tar="vhs_${VHS_VERSION#v}_Linux_$([ "$ARCH" = arm64 ] && echo arm64 || echo x86_64).tar.gz"
  vhs_url="https://github.com/charmbracelet/vhs/releases/download/${VHS_VERSION}"
  curl -fsSL -o "$tmp/$vhs_tar" "$vhs_url/$vhs_tar"
  curl -fsSL "$vhs_url/checksums.txt" | grep " $vhs_tar\$" | (cd "$tmp" && sha256sum -c -) >/dev/null
  tar -xzf "$tmp/$vhs_tar" -C "$tmp"
  sudo install -m 0755 "$(find "$tmp" -name vhs -type f | head -n 1)" /usr/local/bin/vhs
  rm -rf "$tmp"
fi

if [ -f pyproject.toml ]; then
  echo "== uv sync"
  uv sync
fi

v() { printf '%-8s ' "$1"; shift; "$@" 2>&1 | head -n 1 || echo "MISSING"; }
echo
echo "== Tool versions"
v python  python --version
v uv      uv --version
v node    node --version
v npm     npm --version
v claude  claude --version
v docker  docker --version
v kind    kind version
v kubectl kubectl version --client
v helm    helm version --short
v kmcp    kmcp --version
v kagent  kagent version
v jq      jq --version
v curl    curl --version
v vhs     vhs --version
v ttyd    ttyd --version
v ffmpeg  ffmpeg -version
echo
echo "Claude Code config dir: ${CLAUDE_CONFIG_DIR:-~/.claude} (named volume). Run 'claude' to log in."
echo "Keycloak: scripts/keycloak.sh start"
