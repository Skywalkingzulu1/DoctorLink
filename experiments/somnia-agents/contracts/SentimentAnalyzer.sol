// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./interfaces/ISomniaAgents.sol";

contract SentimentAnalyzer {
    IAgentRequester public constant PLATFORM =
        IAgentRequester(0x037Bb9C718F3f7fe5eCBDB0b600D607b52706776);

    uint256 public constant LLM_AGENT_ID = 12847293847561029384;

    enum AnalysisType { Classification, Score }

    struct Analysis {
        string inputText;
        string classification;
        int256 score;
        AnalysisType analysisType;
        uint256 timestamp;
        bool completed;
    }

    mapping(uint256 => Analysis) public analyses;
    string public latestClassification;
    int256 public latestScore;

    event ClassificationRequested(uint256 indexed requestId, string text);
    event ClassificationReceived(uint256 indexed requestId, string classification);
    event ScoreRequested(uint256 indexed requestId, string text);
    event ScoreReceived(uint256 indexed requestId, int256 score);
    event AnalysisFailed(uint256 indexed requestId, ResponseStatus status);

    function classifySentiment(string calldata text) external payable returns (uint256 requestId) {
        string memory prompt = string.concat(
            "Analyze the sentiment of the following text. ",
            "Text: \"", text, "\""
        );

        string[] memory allowedValues = new string[](3);
        allowedValues[0] = "bullish";
        allowedValues[1] = "bearish";
        allowedValues[2] = "neutral";

        bytes memory payload = abi.encodeWithSelector(
            ILLMAgent.inferString.selector,
            prompt,
            "You are a sentiment analyst. Classify the sentiment.",
            false,
            allowedValues
        );

        uint256 deposit = PLATFORM.getRequestDeposit();
        uint256 required = deposit + 0.07 ether * 3; // 0.03 + 0.07*3 = 0.24 STT
        require(msg.value >= required, "Need 0.24 STT total (deposit + 3 validators x 0.07)");

        requestId = PLATFORM.createRequest{value: msg.value}(
            LLM_AGENT_ID,
            address(this),
            this.handleClassification.selector,
            payload
        );

        analyses[requestId] = Analysis({
            inputText: text,
            classification: "",
            score: 0,
            analysisType: AnalysisType.Classification,
            timestamp: block.timestamp,
            completed: false
        });

        emit ClassificationRequested(requestId, text);
    }

    function scoreSentiment(string calldata text) external payable returns (uint256 requestId) {
        string memory prompt = string.concat(
            "Rate the sentiment on a scale of 1-100. ",
            "1 = extremely negative, 50 = neutral, 100 = extremely positive. ",
            "Text: \"", text, "\""
        );

        bytes memory payload = abi.encodeWithSelector(
            ILLMAgent.inferNumber.selector,
            prompt,
            "You are a sentiment analyst. Return only a number.",
            int256(1),
            int256(100),
            false
        );

        uint256 deposit = PLATFORM.getRequestDeposit();
        uint256 required = deposit + 0.07 ether * 3;
        require(msg.value >= required, "Need 0.24 STT total");

        requestId = PLATFORM.createRequest{value: msg.value}(
            LLM_AGENT_ID,
            address(this),
            this.handleScore.selector,
            payload
        );

        analyses[requestId] = Analysis({
            inputText: text,
            classification: "",
            score: 0,
            analysisType: AnalysisType.Score,
            timestamp: block.timestamp,
            completed: false
        });

        emit ScoreRequested(requestId, text);
    }

    function handleClassification(
        uint256 requestId,
        Response[] memory responses,
        ResponseStatus status,
        Request memory
    ) external {
        require(msg.sender == address(PLATFORM), "Only platform");

        if (status == ResponseStatus.Success && responses.length > 0) {
            string memory result = abi.decode(responses[0].result, (string));
            analyses[requestId].classification = result;
            analyses[requestId].completed = true;
            latestClassification = result;
            emit ClassificationReceived(requestId, result);
        } else {
            emit AnalysisFailed(requestId, status);
        }
    }

    function handleScore(
        uint256 requestId,
        Response[] memory responses,
        ResponseStatus status,
        Request memory
    ) external {
        require(msg.sender == address(PLATFORM), "Only platform");

        if (status == ResponseStatus.Success && responses.length > 0) {
            int256 result = abi.decode(responses[0].result, (int256));
            analyses[requestId].score = result;
            analyses[requestId].completed = true;
            latestScore = result;
            emit ScoreReceived(requestId, result);
        } else {
            emit AnalysisFailed(requestId, status);
        }
    }

    function getAnalysis(uint256 requestId) external view returns (Analysis memory) {
        return analyses[requestId];
    }

    function getRequiredDeposit() external view returns (uint256) {
        return PLATFORM.getRequestDeposit();
    }

    receive() external payable {}
}
