from panels import *
# from database_panel_simple import create_database_panel

import dash_mantine_components as dmc
from dash import Dash

app = Dash(__name__, suppress_callback_exceptions=True, assets_folder='assets')
app.title = "sea anemone"


from dash import dcc

import usf
import os

# usf_folders = [
#             #    '/home/matt/geophysics_data/TEM/sTEM_data/2025_0302/USF_Files_dawa river 3/'
#             'C:/Users/au646858/Downloads/USF_Files_dawa river/'
#             ]

# sweeps = []
# for usf_folder in usf_folders:
#     usf_files = [usf_folder+f for f in os.listdir(usf_folder) if f.endswith('.usf')]
#     for usf_file in usf_files:        
#         sweeps += usf.Sweep.from_usf(usf_file, combine=False)

# data_overview, df_data = usf.sweep2dataframes(sweeps)
# data_overview.reset_index(inplace=True)

from pandas import DataFrame
import pandas as pd
df_res = pd.read_csv('inversion_results.csv', index_col=0)
df_overview = df_res.pivot_table(
    index=['site_id'],
    values=['date', 'latitude', 'longitude', 'elevation'],
    aggfunc='first'
)


m1 = Map(data=df_overview)
dbdt1 = dbdtSounding(dataframe=df_res)
dbdt2 = dbdtSection(dataframe=df_res)

u1 = Upload()

t1 = Table(df_overview, id='table_overview')

pivot = df_res.pivot_table(
    index=['site_id'],
    columns='sys_gate',
    values='dbdt'
)



t2 = Table(pivot, id='table_dbdt')

# Create database panel
# db1 = create_database_panel()




panels = [u1, m1, dbdt1, t1, t2, dbdt2]
nodes = [node for panel in panels for node in panel.to_nodes()]
# config = {
#     "global": {"tabEnableClose": True, "tabEnableFloat": True},
#     "borders": [
#         {"type": "border", "location": "right", "size": 200, "children": [                    
#                     {
#                         "type": "tab",
#                         "name": "One",
#                         "component": "text",
#                         "id": "side-1",
#                         "tabEnableClose": False,
#                     },
#         ]},
#     ],
#     "layout": {
#         "type": "column",
#         "weight": 100,
#         "children": [{
#             'type': 'row',
#             "weight": 100,
#             "children": [{
#                 "type": "tabset",
#                 "weight": 50,
#                 "children": [
#                     m1.layout_dict,
#                 ],
#             }]},
#             {
#                 'type': 'row',
#                 "weight": 100,
#                 "children": [{
#                     "type": "tabset",
#                     "weight": 50,
#                     "children": [
#                         dbdt2.layout_dict,
#                         dbdt1.layout_dict,
#                     ],
#                 }]
#             }
#         ],
#     },
# }
config = {
  "global": {
    "tabEnableFloat": True
  },
  "borders": [
    {
      "type": "border",
      "size": 200,
      "location": "right",
      "children": [
        {
          "type": "tab",
          "id": "side-1",
          "name": "One",
          "component": "text"
        }
      ]
    }
  ],
  "layout": {
    "type": "column",
    "id": "#862b2fc6-2ef4-4251-a485-e158ed2bf975",
    "children": [
      {
        "type": "row",
        "id": "#f38c40d3-e354-4752-8bd8-0f924591ece9",
        "children": [
          {
            "type": "tabset",
            "id": "#328817bb-4e54-448e-887f-00356fda1ff9",
            "weight": 50,
            "children": [
              {
                "type": "tab",
                "id": "tab-map",
                "name": "map"
              }
            ],
            "active": True
          },
          {
            "type": "tabset",
            "id": "#6d729cf5-699f-4fad-bdcb-a1bd30574355",
            "weight": 50,
            "children": [
              {
                "type": "tab",
                "id": "tab-tTEM",
                "name": "ttem"
              },
              {
                "type": "tab",
                "id": "tab-sounding",
                "name": "sounding"
              }
            ]
          }
        ]
      }
    ]
  }
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

@app.callback(
    [ 
        Output('sounding', 'figure', allow_duplicate=True),
        Output('tTEM',     'figure', allow_duplicate=True),
    ],
    Input('map', 'selectedData'),
    prevent_initial_call="initial_duplicate",
    allow_duplicate=True
)
def select_from_map(selected_data):
    if not selected_data or 'points' not in selected_data:
        raise PreventUpdate

    selected_points = [-1]+[point['pointIndex'] for point in selected_data['points']]
    new_df = df_res[df_res['site_id'].isin(selected_points)]
    dbdt1.dataframe = new_df
    dbdt2.dataframe = new_df

    return dbdt1.render(), dbdt2.render()

# @app.callback(
#     [ 
#         Output('sounding', 'figure', allow_duplicate=True),
#         Output('tTEM',     'figure', allow_duplicate=True),
#     ],
#     Input('tTEM', 'selectedData'),
#     prevent_initial_call="initial_duplicate",
#     allow_duplicate=True
# )
# def disable_points_from_section(selected_data):
#     if not selected_data or 'points' not in selected_data:
#         raise PreventUpdate
#     data_ids = [point['customdata'][1] for point in selected_data['points'] if 'customdata' in point]

#     df_prev = dbdt2.dataframe
#     df_prev.loc[df_prev['data_id'].isin(data_ids), 'inuse_auto'] = False
#     dbdt1.dataframe = df_prev
#     dbdt2.dataframe = df_prev

#     return dbdt1.render(), dbdt2.render()

@app.callback(
    [ 
        Output('sounding', 'figure', allow_duplicate=True),
        Output('tTEM',     'figure', allow_duplicate=True),
    ],
    Input('sounding', 'selectedData'),
    prevent_initial_call="initial_duplicate",
)
def disable_points_from_sounding(selected_data):
    print('selected data: ', selected_data)
    if not selected_data or 'points' not in selected_data:
        raise PreventUpdate
    data_ids = [point['customdata'][1] for point in selected_data['points'] if 'customdata' in point]

    df_prev = dbdt1.dataframe
    df_prev.loc[df_prev['data_id'].isin(data_ids), 'inuse_auto'] = False
    dbdt1.dataframe = df_prev
    dbdt2.dataframe = df_prev
    return dbdt1.render(), dbdt2.render()

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

# @app.callback(
#     Output('flex-layout', 'id', allow_duplicate=True),  # Dummy output since we just want to print
#     Input('flex-layout', 'model'),
#     prevent_initial_call=True
# )
# def print_layout_changes(layout_model):
#     """Print the layout configuration whenever it changes"""
#     import json
#     print("\n" + "="*50)
#     print("LAYOUT CHANGED:")
#     print("="*50)
#     print(json.dumps(layout_model, indent=2))
#     print("="*50 + "\n")
    
#     # Return the same ID to satisfy the callback requirement
#     return 'flex-layout'



app.run(debug=True, port=8050, dev_tools_hot_reload=True)
#start msedge --app=http://127.0.0.1:8050/