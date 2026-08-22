from langgraph.graph import END, START, StateGraph

from agents.contentgeneration.Node.AssetManager import AssetManagerNode
from agents.contentgeneration.Node.generatecontent import HiggsfieldNode
from agents.contentgeneration.Node.VideoGenerator import VideoGeneratorNode
from agents.contentgeneration.Node.VideoQualityChecker import VideoQualityCheckerNode
from agents.contentgeneration.Node.VisualPromptGenerator import VisualPromptGeneratorNode
from agents.contentgeneration.pipeline_log import with_pipeline_log
from agents.contentgeneration.State.generationstate import VideoState

content_generation_graph = StateGraph(VideoState)
content_generation_graph.add_node("asset_manager", with_pipeline_log("asset_manager", AssetManagerNode))
content_generation_graph.add_node(
    "visual_prompt_generator",
    with_pipeline_log("visual_prompt_generator", VisualPromptGeneratorNode),
)
content_generation_graph.add_node("higgsfield", with_pipeline_log("higgsfield", HiggsfieldNode))
content_generation_graph.add_node("video_generator", with_pipeline_log("video_generator", VideoGeneratorNode))
content_generation_graph.add_node(
    "post_production",
    with_pipeline_log("post_production", VideoQualityCheckerNode),
)
content_generation_graph.add_edge(START, "asset_manager")
content_generation_graph.add_edge("asset_manager", "visual_prompt_generator")
content_generation_graph.add_edge("visual_prompt_generator", "higgsfield")
content_generation_graph.add_edge("higgsfield", "video_generator")
content_generation_graph.add_edge("video_generator", "post_production")
content_generation_graph.add_edge("post_production", END)

content_generation_app = content_generation_graph.compile()
