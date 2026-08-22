from langgraph.graph import END, START, StateGraph

from agents.scriptgenerator.Node.CharacterManager import CharacterManagerNode
from agents.scriptgenerator.Node.ProjectAnalyzer import ProjectAnalyzerNode
from agents.scriptgenerator.Node.ScenePlanner import ScenePlannerNode
from agents.scriptgenerator.Node.ScriptWriter import ScriptWriterNode
from agents.scriptgenerator.pipeline_log import with_pipeline_log
from agents.scriptgenerator.State.scriptstate import ScriptState

script_graph = StateGraph(ScriptState)
script_graph.add_node("project_analyzer", with_pipeline_log("project_analyzer", ProjectAnalyzerNode))
script_graph.add_node("script_writer", with_pipeline_log("script_writer", ScriptWriterNode))
script_graph.add_node("character_manager", with_pipeline_log("character_manager", CharacterManagerNode))
script_graph.add_node("scene_planner", with_pipeline_log("scene_planner", ScenePlannerNode))
script_graph.add_edge(START, "project_analyzer")
script_graph.add_edge("project_analyzer", "script_writer")
script_graph.add_edge("script_writer", "character_manager")
script_graph.add_edge("character_manager", "scene_planner")
script_graph.add_edge("scene_planner", END)

script_generator_app = script_graph.compile()
