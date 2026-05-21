// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./interfaces/ISomniaAgents.sol";

contract PriceOracle {
    IAgentRequester public constant PLATFORM =
        IAgentRequester(0x037Bb9C718F3f7fe5eCBDB0b600D607b52706776);

    uint256 public constant JSON_API_AGENT_ID = 13174292974160097713;

    uint256 public latestPrice;
    uint256 public lastUpdatedAt;
    mapping(uint256 => bool) public pendingRequests;

    event PriceRequested(uint256 indexed requestId, string url, string selector);
    event PriceReceived(uint256 indexed requestId, uint256 price);
    event RequestFailed(uint256 indexed requestId, ResponseStatus status);

    function requestBtcPrice() external payable returns (uint256 requestId) {
        return _requestPrice(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            "bitcoin.usd"
        );
    }

    function requestEthPrice() external payable returns (uint256 requestId) {
        return _requestPrice(
            "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd",
            "ethereum.usd"
        );
    }

    function _requestPrice(string memory url, string memory selector) internal returns (uint256 requestId) {
        bytes memory payload = abi.encodeWithSelector(
            IJsonApiAgent.fetchUint.selector,
            url,
            selector,
            uint8(8)
        );

        uint256 required = PLATFORM.getRequestDeposit() + 0.03 ether * 3;
        require(msg.value >= required, "Need 0.12 STT total (deposit + 3 validators)");

        // Forward all value: deposit is refundable, rest pays validators
        requestId = PLATFORM.createRequest{value: msg.value}(
            JSON_API_AGENT_ID,
            address(this),
            this.handleResponse.selector,
            payload
        );

        pendingRequests[requestId] = true;
        emit PriceRequested(requestId, url, selector);
    }

    function handleResponse(
        uint256 requestId,
        Response[] memory responses,
        ResponseStatus status,
        Request memory
    ) external {
        require(msg.sender == address(PLATFORM), "Only platform");
        require(pendingRequests[requestId], "Unknown request");

        delete pendingRequests[requestId];

        if (status == ResponseStatus.Success && responses.length > 0) {
            latestPrice = abi.decode(responses[0].result, (uint256));
            lastUpdatedAt = block.timestamp;
            emit PriceReceived(requestId, latestPrice);
        } else {
            emit RequestFailed(requestId, status);
        }
    }

    function getFormattedPrice() external view returns (uint256 wholePart, uint256 decimalPart) {
        wholePart = latestPrice / 1e8;
        decimalPart = latestPrice % 1e8;
    }

    function getRequiredDeposit() external view returns (uint256) {
        return PLATFORM.getRequestDeposit();
    }

    receive() external payable {}
}
