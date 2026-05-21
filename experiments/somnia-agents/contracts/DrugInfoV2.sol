// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./interfaces/ISomniaAgents.sol";

contract DrugInfoV2 {
    IAgentRequester public constant PLATFORM =
        IAgentRequester(0x037Bb9C718F3f7fe5eCBDB0b600D607b52706776);

    uint256 public constant LLM_AGENT_ID = 12847293847561029384;

    string[] public drugNames;
    string[] public drugInfo;
    mapping(uint256 => uint256) public requestToInfoIndex;

    event DrugInfoRequested(uint256 indexed requestId, string drugName);
    event DrugInfoReceived(uint256 indexed requestId, string drugName, string info);
    event DrugInfoFailed(uint256 indexed requestId, ResponseStatus status);

    function getDrugInfo(string calldata drugName) external payable returns (uint256 requestId) {
        string memory prompt = string.concat(
            "Provide concise, accurate medical information about ", drugName, ". ",
            "Include: 1) What it is and how it works, 2) Common uses, 3) Typical dosage, ",
            "4) Common side effects, 5) Important precautions. ",
            "Base this on standard medical references. Keep each section to 1-2 sentences."
        );

        bytes memory payload = abi.encodeWithSelector(
            ILLMAgent.inferString.selector,
            prompt,
            "You are a clinical pharmacist providing accurate, evidence-based drug information. Always include a disclaimer to consult a healthcare provider.",
            true,
            new string[](0)
        );

        uint256 deposit = PLATFORM.getRequestDeposit();
        uint256 required = deposit + 0.07 ether * 3;
        require(msg.value >= required, "Need 0.24 STT total");

        requestId = PLATFORM.createRequest{value: msg.value}(
            LLM_AGENT_ID,
            address(this),
            this.handleResult.selector,
            payload
        );

        drugNames.push(drugName);
        drugInfo.push("");
        requestToInfoIndex[requestId] = drugInfo.length - 1;

        emit DrugInfoRequested(requestId, drugName);
    }

    function handleResult(
        uint256 requestId,
        Response[] memory responses,
        ResponseStatus status,
        Request memory
    ) external {
        require(msg.sender == address(PLATFORM), "Only platform");

        uint256 idx = requestToInfoIndex[requestId];

        if (status == ResponseStatus.Success && responses.length > 0) {
            string memory result = abi.decode(responses[0].result, (string));
            drugInfo[idx] = result;
            emit DrugInfoReceived(requestId, drugNames[idx], result);
        } else {
            drugInfo[idx] = "Unable to retrieve drug information at this time.";
            emit DrugInfoFailed(requestId, status);
        }
    }

    function getInfoCount() external view returns (uint256) {
        return drugInfo.length;
    }

    function getInfo(uint256 index) external view returns (string memory drugName, string memory info) {
        return (drugNames[index], drugInfo[index]);
    }

    function getRequiredDeposit() external view returns (uint256) {
        return PLATFORM.getRequestDeposit();
    }

    receive() external payable {}
}
