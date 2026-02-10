from providers.antigravity_provider import AntigravityProvider

def register_providers(server):
    server.add_provider("antigravity", AntigravityProvider())
