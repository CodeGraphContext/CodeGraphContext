// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import {BaseGreeter} from "./BaseGreeter.sol";
import "./MathLib.sol";

contract Greeter is BaseGreeter {
    uint256 public greetCount;

    event Greeted(address indexed who, string message);

    error EmptyName();

    modifier nonEmpty(string memory name) {
        if (bytes(name).length == 0) revert EmptyName();
        _;
    }

    constructor() BaseGreeter("Hello") {}

    function greet(string memory name)
        external
        view
        override
        nonEmpty(name)
        returns (string memory)
    {
        return string(abi.encodePacked(prefix, ", ", name));
    }

    function bump() public {
        greetCount = MathLib.add(greetCount, 1);
        setPrefix(prefix);
        emit Greeted(msg.sender, prefix);
    }

    receive() external payable {}
}
