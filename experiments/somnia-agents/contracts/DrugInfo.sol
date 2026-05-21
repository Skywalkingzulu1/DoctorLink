// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./interfaces/ISomniaAgents.sol";

contract DrugInfo {
    IAgentRequester public constant PLATFORM =
        IAgentRequester(0x037Bb9C718F3f7fe5eCBDB0b600D607b52706776);

    uint256 public constant WEB_AGENT_ID = 12875401142070969085;

    string[] public drugNames;
    string[] public searchResults;
    mapping(uint256 => uint256) public requestToResultIndex;

    event DrugInfoRequested(uint256 indexed requestId, string drugName);
    event DrugInfoReceived(uint256 indexed requestId, string drugName, string result);
    event DrugInfoFailed(uint256 indexed requestId, ResponseStatus status);

    function getDrugInfo(string calldata drugName) external payable returns (uint256 requestId) {
        string memory url = string.concat("https://www.drugs.com/", drugName, ".html");
        string memory prompt = string.concat(
            "Extract the uses, dosage, and side effects of ", drugName,
            " from this page."
        );

        string[] memory options = new string[](0);

        bytes memory payload = abi.encodeWithSelector(
            IParseWebsiteAgent.ExtractString.selector,
            "summary",
            "Uses, dosage, and side effects",
            options,
            prompt,
            url,
            false,    // direct scrape, don't search
            1
        );

        uint256 deposit = PLATFORM.getRequestDeposit();
        uint256 required = deposit + 0.10 ether * 3;
        require(msg.value >= required, "Need 0.33 STT total");

        requestId = PLATFORM.createRequest{value: msg.value}(
            WEB_AGENT_ID,
            address(this),
            this.handleResult.selector,
            payload
        );

        drugNames.push(drugName);
        searchResults.push("");
        requestToResultIndex[requestId] = searchResults.length - 1;

        emit DrugInfoRequested(requestId, drugName);
    }

    function handleResult(
        uint256 requestId,
        Response[] memory responses,
        ResponseStatus status,
        Request memory
    ) external {
        require(msg.sender == address(PLATFORM), "Only platform");

        uint256 idx = requestToResultIndex[requestId];

        if (status == ResponseStatus.Success && responses.length > 0) {
            string memory result = abi.decode(responses[0].result, (string));
            searchResults[idx] = result;
            emit DrugInfoReceived(requestId, drugNames[idx], result);
        } else {
            searchResults[idx] = "Unable to retrieve drug information.";
            emit DrugInfoFailed(requestId, status);
        }
    }

    function getResultCount() external view returns (uint256) {
        return searchResults.length;
    }

    function getResult(uint256 index) external view returns (string memory drugName, string memory result) {
        return (drugNames[index], searchResults[index]);
    }

    function getRequiredDeposit() external view returns (uint256) {
        return PLATFORM.getRequestDeposit();
    }

    receive() external payable {}
}
