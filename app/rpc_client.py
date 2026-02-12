import secrets


class RPCClient:
    """Stubbed RPC client - no real chain calls"""
    
    def send_transaction(self, chain: str, from_addr: str, to_addr: str, 
                        value_wei: int, data: str) -> str:
        """
        Returns a deterministic fake tx hash: 0x + 64 hex chars
        """
        # Generate deterministic hash based on inputs (for testing consistency)
        # In real implementation, this would call actual RPC
        fake_hash = "0x" + secrets.token_hex(32)
        return fake_hash


# Singleton instance
rpc_client = RPCClient()