## Requirement: named levels with capability matrices

The platform SHALL publish exactly the named levels with their filesystem, network, process, secret, and persistence rights. A workload SHALL NOT receive rights outside its level's matrix.

### Scenario: observer attempts write

Given a workload at observer level, when it attempts a filesystem write, then the write SHALL fail and the attempt SHALL be recorded.

### Scenario: restricted attempts egress

Given a restricted workload, when it attempts a network connection outside its declared egress, then the connection SHALL fail and the attempt SHALL be evidence.

## Requirement: declared level enforcement

A workload SHALL declare its required level in the bundle. The runtime SHALL enforce that level or SHALL refuse to run the workload.

### Scenario: host cannot enforce contained

Given a host lacking the container mechanism, when a contained-level workload is requested, then the runtime SHALL refuse with an explicit diagnostic and SHALL NOT run it weaker.

## Requirement: fail-closed containment

Any containment mechanism fault SHALL stop the workload, produce an ERROR verdict, and emit evidence naming the fault.

### Scenario: runtime enforcement error

Given a seccomp or mount failure mid-workload, when the fault occurs, then execution SHALL halt and the run SHALL NOT produce a passing verdict.
