"""Exercise operation parameter name validation using synthetic values."""
import json

from fleet_manager.operations import (
    Operation,
    OperationKind,
    OperationRefused,
    Subject,
    SubjectKind,
)


class MeasuredValue(str):
    length_calls = 0

    def __len__(self):
        type(self).length_calls += 1
        return super().__len__()


def attempt(kind, parameters):
    try:
        Operation(
            operation_key="op-1",
            host_id="host-a",
            kind=kind,
            subject=Subject(kind=SubjectKind.RUNNER, subject_id="runner-a"),
            issued_at="2026-10-24T06:00:00Z",
            parameters=parameters,
        )
    except OperationRefused as exc:
        return {"result": "rejected", "reason": str(exc)}
    return {"result": "accepted"}


valid_string = attempt(OperationKind.DESTROY_RUNNER, (("command", "synthetic-value"),))
non_string = attempt(OperationKind.DESTROY_RUNNER, (("command", 42),))
MeasuredValue.length_calls = 0
prior_value = attempt(
    OperationKind.CREATE_RUNNER,
    (("pool_id", MeasuredValue("pool-a")), ("command", "synthetic-value")),
)
results = {
    "forbidden_name_string_value": valid_string,
    "forbidden_name_non_string_value": non_string,
    "forbidden_name_after_measured_value": {
        **prior_value,
        "earlier_value_length_calls": MeasuredValue.length_calls,
    },
}
assert "remote shell" in valid_string["reason"]
assert "pair of strings" in non_string["reason"]
assert "command" not in non_string["reason"]
assert "remote shell" in prior_value["reason"]
assert MeasuredValue.length_calls > 0
print(json.dumps(results, indent=2, sort_keys=True))
