# Sample Solidity project fixture

Minimal multi-file Solidity sample used by unit tests and local index smoke checks.

| File | Role |
|------|------|
| `IGreeter.sol` | Interface |
| `BaseGreeter.sol` | Abstract contract + relative import |
| `MathLib.sol` | Library |
| `Greeter.sol` | Named import, inheritance, calls, modifier, event, error, `receive` |
| `UsingCounter.sol` | `using MathLib for uint256` member-call rewrite |
