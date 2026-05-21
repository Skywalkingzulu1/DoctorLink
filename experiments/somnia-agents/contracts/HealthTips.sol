// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./interfaces/ISomniaAgents.sol";

contract HealthTips {
    IAgentRequester public constant PLATFORM =
        IAgentRequester(0x037Bb9C718F3f7fe5eCBDB0b600D607b52706776);

    uint256 public constant LLM_AGENT_ID = 12847293847561029384;

    string[] public topics;
    string[] public tips;
    mapping(uint256 => uint256) public requestToTipIndex;

    event TipRequested(uint256 indexed requestId, string topic);
    event TipReceived(uint256 indexed requestId, string topic, string tip);
    event TipFailed(uint256 indexed requestId, ResponseStatus status);

    function getHealthTip(string calldata topic) external payable returns (uint256 requestId) {
        string memory prompt = string.concat(
            "Give a concise, evidence-based health tip about: ", topic, ". ",
            "Keep it to 1-2 sentences. Do not include disclaimers."
        );

        bytes memory payload = abi.encodeWithSelector(
            ILLMAgent.inferString.selector,
            prompt,
            "You are a helpful health assistant providing accurate, evidence-based health tips.",
            true,
            new string[](0)
        );

        uint256 deposit = PLATFORM.getRequestDeposit();
        uint256 required = deposit + 0.07 ether * 3; // LLM agent = 0.07 STT/validator
        require(msg.value >= required, "Need 0.24 STT total");

        requestId = PLATFORM.createRequest{value: msg.value}(
            LLM_AGENT_ID,
            address(this),
            this.handleTip.selector,
            payload
        );

        topics.push(topic);
        tips.push("");
        requestToTipIndex[requestId] = tips.length - 1;

        emit TipRequested(requestId, topic);
    }

    function handleTip(
        uint256 requestId,
        Response[] memory responses,
        ResponseStatus status,
        Request memory
    ) external {
        require(msg.sender == address(PLATFORM), "Only platform");

        uint256 idx = requestToTipIndex[requestId];

        if (status == ResponseStatus.Success && responses.length > 0) {
            string memory tip = abi.decode(responses[0].result, (string));
            tips[idx] = tip;
            emit TipReceived(requestId, topics[idx], tip);
        } else {
            tips[idx] = "Unable to generate tip at this time.";
            emit TipFailed(requestId, status);
        }
    }

    function getTipCount() external view returns (uint256) {
        return tips.length;
    }

    function getTip(uint256 index) external view returns (string memory topic, string memory tip) {
        return (topics[index], tips[index]);
    }

    function getRequiredDeposit() external view returns (uint256) {
        return PLATFORM.getRequestDeposit();
    }

    receive() external payable {}
}
