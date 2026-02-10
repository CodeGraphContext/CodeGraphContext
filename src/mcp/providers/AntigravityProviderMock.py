class AntigravityProviderMock:
    """
    Mock provider for Google Antigravity.
    Used by contributors who don't have access to real API keys.
    Simulates responses so MCP server wiring can be tested.
    """

    def fetch_context(self, resource: str, params: dict = None):
        """
        Return fake data for the requested resource.
        """
        return {
            "resource": resource,
            "params": params or {},
            "data": f"Mocked {resource} data from Antigravity"
        }

    def list_resources(self):
        """
        List the resources this mock can pretend to provide.
        """
        return ["schema", "logs", "workflow", "metrics"]

    def __repr__(self):
        return "<AntigravityProviderMock>"
