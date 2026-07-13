# Sample Foundry remappings fixture

Synthetic Foundry-style layout for Solidity remapping tests.

- `foundry.toml` maps `forge-std/` → `lib/helper/src/`
- `src/App.sol` imports `forge-std/Helper.sol`
- `lib/helper/src/Helper.sol` provides `Helper.ping`
