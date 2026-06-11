"""AquaTrade research pipelines."""

__all__ = ["QuantFlowPipeline"]


def __getattr__(name: str):
    if name == "QuantFlowPipeline":
        from .quant_flow_pipeline import QuantFlowPipeline

        return QuantFlowPipeline
    raise AttributeError(name)
