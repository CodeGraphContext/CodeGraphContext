// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "./MathLib.sol";

contract UsingCounter {
    using MathLib for uint256;

    uint256 public value;

    function bump() public {
        value = value.add(1);
    }
}
