from langgraph.graph import END, START, StateGraph

from agents.outreach.nodes.connect import ConnectNode
from agents.outreach.nodes.note import NoteNode
from agents.outreach.nodes.open_profile import OpenProfileNode
from agents.outreach.nodes.send_message import SendMessageNode
from agents.outreach.pipeline_log import with_pipeline_log
from agents.outreach.state.outreachstate import OutreachState

outreach_graph = StateGraph(OutreachState)

outreach_graph.add_node("open_profile", with_pipeline_log("open_profile", OpenProfileNode))
outreach_graph.add_node("connect", with_pipeline_log("connect", ConnectNode))
outreach_graph.add_node("note", with_pipeline_log("note", NoteNode))
outreach_graph.add_node("send_message", with_pipeline_log("send_message", SendMessageNode))

outreach_graph.add_edge(START, "open_profile")
outreach_graph.add_edge("open_profile", "connect")
outreach_graph.add_edge("connect", "note")
outreach_graph.add_edge("note", "send_message")
outreach_graph.add_edge("send_message", END)

outreach_graph_app = outreach_graph.compile()
