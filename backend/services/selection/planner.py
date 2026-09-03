class ClipPlanner:
    MIN_CLIP_DURATION = 2.0
    MAX_CLIP_DURATION = 60.0

    def __init__(self):
        pass

    def plan_clip(self, mapping, source):
        # By default, use what's already mapped if it's there
        start = mapping.start_timestamp
        end = mapping.end_timestamp

        if start is None or end is None:
            return None, None, "UNKNOWN", "Timestamps unavailable; source exceeds maximum clip duration or explicit boundaries missing"

        # Validate types and ranges
        try:
            start = float(start)
            end = float(end)
        except (ValueError, TypeError):
            return None, None, "UNKNOWN", "Invalid timestamp types"

        if start < 0:
            return None, None, "UNKNOWN", "Negative start timestamp"
        
        if end <= start:
            return None, None, "UNKNOWN", "End timestamp must be strictly greater than start timestamp"

        duration = end - start
        if duration < self.MIN_CLIP_DURATION:
            return None, None, "UNKNOWN", f"Duration {duration} below minimum {self.MIN_CLIP_DURATION}"
            
        if duration > self.MAX_CLIP_DURATION:
            return None, None, "UNKNOWN", f"Duration {duration} above maximum {self.MAX_CLIP_DURATION}"

        if source.source_duration and end > source.source_duration:
            return None, None, "UNKNOWN", f"End timestamp {end} exceeds source duration {source.source_duration}"

        return start, end, "HUMAN_PROVIDED", "Human-provided clip boundaries validated successfully"
