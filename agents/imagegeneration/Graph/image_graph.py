from langgraph.graph import END, START, StateGraph

from agents.imagegeneration.Node.GeminiImageGenerator import GeminiImageGeneratorNode
from agents.imagegeneration.Node.PromptBuilder import PromptBuilderNode
from agents.imagegeneration.pipeline_log import with_pipeline_log
from agents.imagegeneration.State.imagestate import ImageState

image_graph = StateGraph(ImageState)
image_graph.add_node("prompt_builder", with_pipeline_log("prompt_builder", PromptBuilderNode))
image_graph.add_node(
    "gemini_image_generator",
    with_pipeline_log("gemini_image_generator", GeminiImageGeneratorNode),
)
image_graph.add_edge(START, "prompt_builder")
image_graph.add_edge("prompt_builder", "gemini_image_generator")
image_graph.add_edge("gemini_image_generator", END)

image_generation_app = image_graph.compile()
