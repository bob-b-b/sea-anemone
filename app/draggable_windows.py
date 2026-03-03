# """
# Draggable popup windows for Sea Anemone.

# Ported from the GIS branch's Sections_plotting.py.
# """

# from dash import html, dcc


# def create_draggable_window(win_id, title, content, width="400px", height="700px"):

#     if hasattr(content, "layout"):
#         # It's a Plotly figure – wrap it
#         body = dcc.Graph(
#             figure=content,
#             style={"height": "100%", "width": "100%"},
#             config={"responsive": True, "displayModeBar": True},
#         )
#     else:
#         body = content

#     return html.Div(
#         id=win_id,
#         className="draggable-window",
#         style={
#             "position": "fixed",
#             "top": "150px",
#             "left": "200px",
#             "width": width,
#             "height": height,
#             "backgroundColor": "white",
#             "border": "2px solid #333",
#             "zIndex": 1000,
#             "resize": "both",
#             "overflow": "hidden",
#             "display": "flex",
#             "flexDirection": "column",
#             "boxShadow": "8px 8px 20px rgba(0,0,0,0.4)",
#         },
#         children=[
#             html.Div(
#                 [
#                     html.Span(
#                         title,
#                         style={"fontWeight": "bold", "marginLeft": "10px"},
#                     ),
#                     html.Button(
#                         "✕",
#                         id={"type": "close-window", "index": win_id},
#                         style={
#                             "float": "right",
#                             "cursor": "pointer",
#                             "color": "white",
#                             "border": "none",
#                             "background": "none",
#                         },
#                     ),
#                 ],
#                 className="window-header",
#                 style={
#                     "background": "#2c3e50",
#                     "color": "white",
#                     "padding": "5px",
#                     "height": "30px",
#                     "cursor": "move",
#                 },
#             ),
#             html.Div(
#                 body,
#                 style={"flex": "1 1 auto", "minHeight": "0", "width": "100%"},
#             ),
#         ],
#     )
