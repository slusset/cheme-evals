Feature: Run Traceability
  To keep the eval harness auditable and replayable
  As a researcher
  I want each run to emit stable IDs and append-only trace records

  Scenario: Mock-backed fixture run writes a result and trace
    Given a fixture with a saved mock response
    When the harness runs the fixture in mock mode
    Then the result includes a stable run_id
    And a trace file is created for that run_id
    And the trace contains ordered lifecycle events
    And the archive ledger records the completed run

  Scenario: Mock mode fails fast when the mock is missing
    Given a fixture without a saved mock response
    When the harness is asked to run in mock mode
    Then the run fails with a missing mock error
    And no live provider call is made

  Scenario: Proposal-aware run emits artifact trace events
    Given a fixture run that produces a tool proposal
    When the harness records the run
    Then the trace contains an artifact_proposed event
    And the event links to the artifact record
    And the artifact record links back to the source run
