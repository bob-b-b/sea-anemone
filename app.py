from panels import *
# from database_panel_simple import create_database_panel

import dash_mantine_components as dmc
from dash import Dash

app = Dash(__name__, suppress_callback_exceptions=True, assets_folder='assets')
app.title = "sea anemone"


from dash import dcc

import usf
import os

usf_folders = [
               '/home/matt/geophysics_data/TEM/sTEM_data/2025_0302/USF_Files_dawa river 3/'
            ]

sweeps = []
for usf_folder in usf_folders:
    usf_files = [usf_folder+f for f in os.listdir(usf_folder) if f.endswith('.usf')]
    for usf_file in usf_files:        
        sweeps += usf.Sweep.from_usf(usf_file, combine=False)

data_overview, df_data = usf.sweep2dataframes(sweeps)
data_overview.reset_index(inplace=True)

m1 = Map(data=data_overview)
# dbdt1 = dbdtSounding(lm_time=ep.lm.time.mean(0),
#                     lm_data=ep.lm.data.mean(0),
#                     hm_time=ep.hm.time.mean(0),
#                     hm_data=ep.hm.data.mean(0))

# rhoa1 = rhoaSounding(lm_time=ep.lm.time.mean(0),
#                     lm_data=ep.lm.data.mean(0),
#                     hm_time=ep.hm.time.mean(0),
#                     hm_data=ep.hm.data.mean(0))


# dbdt2 = dbdtSection(lm_time=ep.lm.time,
#                 lm_data=ep.lm.data,
#                 hm_time=ep.hm.time,
#                 hm_data=ep.hm.data)

u1 = Upload()

t1 = Table(data_overview, id='table_overview')

df_data['sys_gate'] = df_data['system_id'].astype(str) + '-' + df_data['gate_id'].astype(str)
pivot = df_data.pivot_table(
    index=['site_id'],
    columns='sys_gate',
    values='dbdt'
)



t2 = Table(pivot, id='table_dbdt')

# Create database panel
# db1 = create_database_panel()




panels = [u1, m1, t1, t2]
nodes = [node for panel in panels for node in panel.to_nodes()]
config = {
    "global": {"tabEnableClose": True, "tabEnableFloat": True},
    "borders": [
        {"type": "border", "location": "right", "size": 200, "children": [                    
                    {
                        "type": "tab",
                        "name": "One",
                        "component": "text",
                        "id": "side-1",
                        "tabEnableClose": False,
                    },
        ]},
    ],
    "layout": {
        "type": "row",
        "weight": 100,
        "children": [{
                "type": "tabset",
                "weight": 50,
                "children": [
                    u1.layout_dict,
                    m1.layout_dict,
                    t1.layout_dict,
                ],
            },
            {
                "type": "tabset",
                "weight": 50,
                "children": [
                    t2.layout_dict,
                ],
            },
        ],
    },
}

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dfl.FlexLayout(
    id="flex-layout",
    model=config,
    children=nodes,
    useStateForModel=False,
    
)]
)

for panel in panels:
    panel.add_callbacks(app)

# @app.callback(
#     [ 
#         Output('sounding', 'figure', allow_duplicate=True),
#         Output('tTEM',     'figure', allow_duplicate=True),
#         Output('rhoa',     'figure', allow_duplicate=True)
#     ],
#     Input('map', 'selectedData'),
#     prevent_initial_call="initial_duplicate",
#     allow_duplicate=True
# )
# def update_dbdt(selected_data):
#     if not selected_data or 'points' not in selected_data:
#         raise PreventUpdate

#     # Extract selected points
#     selected_points = [point['pointIndex'] for point in selected_data['points']]

#     dbdt1.hm_data = ep.hm.data[selected_points]*1.
#     dbdt1.lm_data = ep.lm.data[selected_points]*1.
    
#     rhoa1.hm_data = ep.hm.data[selected_points]*1.
#     rhoa1.lm_data = ep.lm.data[selected_points]*1.        

#     dbdt2.hm_data = ep.hm.data[selected_points]*1.
#     dbdt2.lm_data = ep.lm.data[selected_points]*1.
#     dbdt2.hm_time = ep.hm.time[selected_points]*1.
#     dbdt2.lm_time = ep.lm.time[selected_points]*1.
#     return dbdt1.render(), dbdt2.render(), rhoa1.render()

# @app.callback(
#     [
#         Output('sounding', 'figure', allow_duplicate=True),
#         Output('tTEM',     'figure', allow_duplicate=True),
#         Output('rhoa',     'figure', allow_duplicate=True),
#         # Output('table', 'children', allow_duplicate=True)
#     ],
#     Input('map', 'selectedData'),
#     prevent_initial_call="initial_duplicate",
#     allow_duplicate=True
# )
# def select_from_map(selected_data):
#     if not selected_data or 'points' not in selected_data:
#         raise PreventUpdate


#     selected_points = [point['pointIndex'] for point in selected_data['points']]
#     # t1.selected_rows = selected_points

#     tmp_hm  = ep.hm.data[selected_points]*1.
#     tmp_lm  = ep.lm.data[selected_points]*1.

#     dbdt1.hm_data = tmp_hm
#     dbdt1.lm_data = tmp_lm

#     rhoa1.hm_data = tmp_hm
#     rhoa1.lm_data = tmp_lm
#     dbdt2.hm_data = tmp_hm
#     dbdt2.lm_data = tmp_lm

#     dbdt2.hm_time = ep.hm.time[selected_points]*1.
#     dbdt2.lm_time = ep.lm.time[selected_points]*1.
#     return dbdt1.render(), dbdt2.render(), rhoa1.render()

# @app.callback(
#     [
#         Output('sounding', 'figure', allow_duplicate=True),
#         Output('tTEM',     'figure', allow_duplicate=True),
#         Output('rhoa',     'figure', allow_duplicate=True),
#         # Output('map', 'selectedData', allow_duplicate=True)
#     ],
#     Input('table', 'selected_data'),
#     prevent_initial_call="initial_duplicate",
# )
# def select_from_table(selected_data):
#     print('selected data: ', selected_data)
    # if not selected_data or 'points' not in selected_data:
    #     raise PreventUpdate

    # row_ids = [cell['row'] for cell in selected_data if 'row' in cell]
    # # Extract selected points
    # selected_points = [point['pointIndex'] for point in selected_data['points']]

    # tmp_hm  = ep.hm.data[selected_points]*1.
    # tmp_lm  = ep.lm.data[selected_points]*1.

    # dbdt1.hm_data = tmp_hm
    # dbdt1.lm_data = tmp_lm

    # rhoa1.hm_data = tmp_hm
    # rhoa1.lm_data = tmp_lm
    # dbdt2.hm_data = tmp_hm
    # dbdt2.lm_data = tmp_lm

    # dbdt2.hm_time = ep.hm.time[selected_points]*1.
    # dbdt2.lm_time = ep.lm.time[selected_points]*1.
    # return dbdt1.render(), dbdt2.render(), rhoa1.render()





app.run(debug=True, port=8050, dev_tools_hot_reload=True)
#start msedge --app=http://127.0.0.1:8050/