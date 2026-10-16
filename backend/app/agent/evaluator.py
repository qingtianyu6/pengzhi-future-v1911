from datetime import datetime, UTC


def evaluate(baseline, reading, target, due_at):
    metric = target['metric']
    before = baseline.get(metric)
    after = reading.get(metric) if reading else None
    timestamp = reading.get('recorded_at') if reading else None
    stamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00')) if timestamp else None
    due = due_at.replace(tzinfo=UTC) if due_at.tzinfo is None else due_at
    fresh = bool(stamp and (stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else stamp) >= due)
    now = datetime.now(UTC)
    normalized_stamp = (stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else stamp) if stamp else None
    recent = bool(normalized_stamp and 0 <= (now - normalized_stamp).total_seconds() <= 3600)
    valid = bool(reading and reading.get('quality_flag') == 'valid' and fresh and recent and after is not None)
    return {'metric': metric, 'before': before, 'after': after,
            'delta': round(after - before, 3) if valid and before is not None else None,
            'target_min': target['target_min'], 'target_max': target['target_max'],
            'fresh': fresh, 'achieved': valid and target['target_min'] <= after <= target['target_max'],
            'data_status': 'available' if valid else 'insufficient_data',
            'notice': '环境前后变化不证明任务操作的因果关系。'}
