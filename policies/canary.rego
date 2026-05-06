package swiftdeploy.canary

supported_question if input.question == "pre_promote"

supported_question if input.question == "status"

violations := [violation | violation := deny[_]]

reason := "canary safety policy passed" if {
	count(violations) == 0
}

reason := sprintf("canary safety policy denied: %v violation(s)", [count(violations)]) if {
	count(violations) > 0
}

decision := {
	"domain": "canary",
	"question": input.question,
	"allowed": count(violations) == 0,
	"reason": reason,
	"violations": violations,
	"observed": {
		"error_rate": input.metrics.error_rate,
		"p99_latency_seconds": input.metrics.p99_latency_seconds,
		"window_seconds": input.metrics.window_seconds,
	},
}

deny contains {
	"id": "unsupported_question",
	"message": sprintf("canary policy does not answer question %q", [input.question]),
	"observed": input.question,
} if {
	not supported_question
}

deny contains {
	"id": "error_rate_too_high",
	"message": sprintf("error rate %.4f is above allowed %.4f", [input.metrics.error_rate, input.thresholds.max_error_rate]),
	"observed": input.metrics.error_rate,
	"threshold": input.thresholds.max_error_rate,
} if {
	supported_question
	input.metrics.error_rate > input.thresholds.max_error_rate
}

deny contains {
	"id": "p99_latency_too_high",
	"message": sprintf("p99 latency %.3fs is above allowed %.3fs", [input.metrics.p99_latency_seconds, input.thresholds.max_p99_latency_seconds]),
	"observed": input.metrics.p99_latency_seconds,
	"threshold": input.thresholds.max_p99_latency_seconds,
} if {
	supported_question
	input.metrics.p99_latency_seconds > input.thresholds.max_p99_latency_seconds
}
