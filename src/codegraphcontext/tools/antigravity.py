class AntigravityProvider:
    def __init__(self, config):
        self.config = config

    def get_context(self, query):
        # Example: fetch schema/logs from Antigravity
        return {"result": f"Antigravity context for {query}"}

