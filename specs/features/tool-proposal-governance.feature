Feature: Tool Proposal Governance
  To evolve the harness safely
  As a builder
  I want tool proposals to be recorded, scored, and promoted explicitly

  Scenario: Required proposal is scored as present
    Given a fixture whose proposal expectation mode is required
    And the agent proposes the expected blocking tool
    When the harness scores the run
    Then the proposal quality score is 100 percent

  Scenario: Unnecessary proposal is penalized
    Given a fixture whose proposal expectation mode is unnecessary
    And the agent proposes a tool anyway
    When the harness scores the run
    Then the proposal quality score is 0 percent

  Scenario: Optional proposal allows either path
    Given a fixture whose proposal expectation mode is optional
    When the agent proposes the expected tool
    Then the proposal quality score is 100 percent
    When the agent proposes no tool
    Then the proposal quality score is 100 percent

  Scenario: Artifact lifecycle transition is explicit
    Given a proposed tool artifact exists
    When a reviewer validates the artifact
    Then the artifact status becomes validated
    And an artifact transition record is appended to the archive ledger
    When a reviewer promotes the artifact
    Then the artifact status becomes promoted

  Scenario: Invalid artifact transition is rejected
    Given a proposed tool artifact exists
    When a reviewer attempts to promote it directly
    Then the harness rejects the transition
