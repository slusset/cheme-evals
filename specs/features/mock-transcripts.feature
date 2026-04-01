Feature: Canonical Mock Transcript Coverage
  To keep offline validation manageable
  As a harness maintainer
  I want a finite set of named transcript stories that cover important protocol transitions

  Scenario: Direct solve transcript exists
    Given a fixture or mock that yields a final answer without tool use
    When the harness replays that transcript
    Then the run completes with a result, trace, and archive record

  Scenario: Proposal transcript exists
    Given a transcript where the model emits propose_tool
    When the harness replays that interaction
    Then a tool proposal is recorded
    And an artifact record is created
    And the run still reaches a final answer

  Scenario: Strict mock replay exists
    Given a run requested in mock mode
    When the mock transcript is missing
    Then the harness fails rather than calling a live model

  Scenario: Future transcript backlog is explicit
    Given the state machine contains branches not yet covered by offline replay
    Then those branches are listed as hypotheses
    And they are not treated as confirmed coverage
