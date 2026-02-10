import os
import requests

class AntigravityProvider:
    """
    Provider class to integrate Google Antigravity with MCP server.
    Exposes methods to fetch context, schemas, and logs.
    """

    def __init__(self):
        # Load API key from environment variables
        self.api_key = os.getenv("ANTIGRAVITY_API_KEY")
        self.endpoint = "https://antigravity.googleapis.com/v1/context"

        if not self.api_key:
            raise ValueError("Missing ANTIGRAVITY_API_KEY in environment variables")

    def fetch_context(self, resource: str, params: dict = None):
        """
        Fetch live context from Antigravity.
        :param resource: type of resource (e.g., 'schema', 'logs', 'workflow')
        :param params: optional query parameters
        :return: JSON response from Antigravity
        """
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"{self.endpoint}/{resource}"

        response = requests.get(url, headers=headers, params=params or {})
        response.raise_for_status()
        return response.json()

    def list_resources(self):
        """
        List available resources Antigravity can provide.
        """
        return ["schema", "logs", "workflow", "metrics"]

    def __repr__(self):
        return "<AntigravityProvider connected>"
