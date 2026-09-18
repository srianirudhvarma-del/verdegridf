from shared.classification import (
    WorkloadClassificationStore,
    is_deferrable,
    resolve_classification,
)
from shared.contracts import WorkloadTag


def make_tag(workload_id, classification, max_delay=None, source="operator"):
    return WorkloadTag(
        workloadId=workload_id,
        classification=classification,
        maxDelayMinutes=max_delay,
        source=source,
        updatedAt="2026-08-25T00:00:00Z",
    )


def test_missing_tag_resolves_to_protected():
    assert resolve_classification(None) == "protected"
    assert is_deferrable(None) is False


def test_unclassified_tag_resolves_to_protected():
    tag = make_tag("vm-1", "unclassified")
    assert resolve_classification(tag) == "protected"


def test_explicit_deferrable_tag_resolves_to_deferrable():
    tag = make_tag("vm-2", "deferrable", max_delay=30)
    assert resolve_classification(tag) == "deferrable"
    assert is_deferrable(tag) is True


def test_store_untagged_workload_is_protected():
    store = WorkloadClassificationStore()
    assert store.classification_for("vm-unknown") == "protected"
    assert store.is_deferrable("vm-unknown") is False


def test_store_returns_operator_set_classification():
    store = WorkloadClassificationStore()
    store.set_tag(make_tag("vm-3", "deferrable", max_delay=60))
    assert store.classification_for("vm-3") == "deferrable"
    assert store.is_deferrable("vm-3") is True


def test_store_reclassification_overwrites_previous_tag():
    store = WorkloadClassificationStore()
    store.set_tag(make_tag("vm-4", "deferrable", max_delay=15))
    assert store.is_deferrable("vm-4") is True

    store.set_tag(make_tag("vm-4", "protected"))
    assert store.is_deferrable("vm-4") is False


def test_store_shared_across_lookups_reflects_latest_state():
    """Simulates two 'modules' reading through the same store instance."""
    store = WorkloadClassificationStore()
    idlehunter_view_before = store.classification_for("vm-5")
    store.set_tag(make_tag("vm-5", "deferrable", max_delay=45, source="inferred"))
    gridsync_view_after = store.classification_for("vm-5")

    assert idlehunter_view_before == "protected"
    assert gridsync_view_after == "deferrable"
