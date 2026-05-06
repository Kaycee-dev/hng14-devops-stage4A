package swiftdeploy.infrastructure

supported_question if input.question == "pre_deploy"

supported_question if input.question == "status"

violations := [violation | violation := deny[_]]

reason := "infrastructure policy passed" if {
	count(violations) == 0
}

reason := sprintf("infrastructure policy denied: %v violation(s)", [count(violations)]) if {
	count(violations) > 0
}

decision := {
	"domain": "infrastructure",
	"question": input.question,
	"allowed": count(violations) == 0,
	"reason": reason,
	"violations": violations,
	"observed": {
		"disk_free_gb": input.host.disk_free_gb,
		"cpu_load": input.host.cpu_load,
	},
}

deny contains {
	"id": "unsupported_question",
	"message": sprintf("infrastructure policy does not answer question %q", [input.question]),
	"observed": input.question,
} if {
	not supported_question
}

deny contains {
	"id": "disk_free_too_low",
	"message": sprintf("disk free %vGB is below required %vGB", [input.host.disk_free_gb, input.thresholds.min_disk_free_gb]),
	"observed": input.host.disk_free_gb,
	"threshold": input.thresholds.min_disk_free_gb,
} if {
	supported_question
	input.host.disk_free_gb < input.thresholds.min_disk_free_gb
}

deny contains {
	"id": "cpu_load_too_high",
	"message": sprintf("cpu load %v is above allowed %v", [input.host.cpu_load, input.thresholds.max_cpu_load]),
	"observed": input.host.cpu_load,
	"threshold": input.thresholds.max_cpu_load,
} if {
	supported_question
	input.host.cpu_load > input.thresholds.max_cpu_load
}
