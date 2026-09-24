// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

interface IGreeter {
    function greet(string memory name) external view returns (string memory);
}
