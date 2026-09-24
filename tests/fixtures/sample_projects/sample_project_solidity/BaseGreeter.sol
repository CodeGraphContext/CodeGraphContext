// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "./IGreeter.sol";

abstract contract BaseGreeter is IGreeter {
    string internal prefix;

    constructor(string memory initialPrefix) {
        prefix = initialPrefix;
    }

    function setPrefix(string memory newPrefix) public virtual {
        prefix = newPrefix;
    }
}
