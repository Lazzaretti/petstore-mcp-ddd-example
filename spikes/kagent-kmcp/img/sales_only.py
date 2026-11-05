# One bounded context per container: serve sales at /mcp (kagent derives http://<name>.<ns>:<port>/mcp for MCPServer)
from app import sales
app = sales.http_app(path="/mcp")
