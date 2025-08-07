from panels import *
# from database_panel_simple import create_database_panel
from dash import dcc
import pandas as pd
import dash_mantine_components as dmc
from dash import Dash, callback_context
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

external_stylesheets = [dbc.themes.BOOTSTRAP]
app = Dash(__name__, suppress_callback_exceptions=True, assets_folder='assets',  external_stylesheets=external_stylesheets)
app.title = "sea anemone"



df_res = pd.read_csv('./prototyping/inversion_results.csv', index_col=0)
print(df_res.columns)
df_mod = pd.read_csv('./prototyping/inversion_results_models.csv')

df_overview = df_res.pivot_table(
    index=['site_id'],
    values=['date', 'daytime', 'latitude', 'longitude', 'elevation'],
    aggfunc='first'
)
df_overview['site_id'] = df_overview.index

def calculate_inuse(inuse_auto, inuse_manual):
    # inuse = inuse_auto.copy()
    # inuse[inuse_manual.notna()] = inuse_manual[inuse_manual.notna()]
    return inuse_manual.fillna(inuse_auto)

df_res['include'] = calculate_inuse(df_res['inuse_auto'], df_res['inuse_manual'])

m1 = Map(data=df_overview)
dbdt1 = dbdtSounding(dataframe=df_res)
dbdt2 = dbdtSection(dataframe=df_res)

m1.highlighted = 16

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

mod1 = ModelGraph(dataframe=df_mod)
mod2 = ModelSection(dataframe=df_mod)

x = html.Div([
      dcc.Markdown(children='## buttons and hot keys'),
      html.Button("disable [ctrl+d]", id='disableButton'),
      html.Button("enable  [ctrl+e]", id='enableButton'),
    ]
, id='processing_buttons')


stmod = StartingModel.standard()

panels = [u1, m1, dbdt1, t1, t2, dbdt2, mod1, mod2, stmod]
nodes = [node for panel in panels for node in panel.to_nodes()]+[dfl.Tab(id=f'tab-processing_buttons', children=[x]), dfl.Tab(id='tab-panel_list', children=[panel_list])]


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
    "tabEnableFloat":  False,
    "tabEnableClose":  True,
    "tabEnableDrag":   True,
    "tabEnableResize": True,

  },
  "borders": [
    {
      "type": "border",
      "size": 200,
      "location": "left",
      "children": [
        {
          "type": "tab",
          "id": "tab-panel_list",
          "name": "Panels",
          "component": "text"
        }
      ]
    },
    {
      "type": "border",
      "selected": 0,
      "size": 200,
      "location": "bottom",
      "children": [
        {
          "type": "tab",
          "id": "tab-processing_buttons",
          "name": "buttons",
        }
      ],
      "active": True
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
              m1.layout_dict,
              u1.layout_dict,              
            ],
          },
          {
            "type": "tabset",
            "id": "#b0c1f8d2-3e4a-4c5b-9f6d-7e8f9a0b1c2d",
            "weight": 50,
            "children": [
                {
                    "type": "tab",
                    "id": "tab-model_section",
                    "name": "model section"
                },
                {
                    "type": "tab",
                    "id": "tab-model_graph",
                    "name": "models"
                }
              ]          
          },
          {
            "type": "tabset",
            "id": "#6d729cf5-699f-4fad-bdcb-a1bd30574355",
            "weight": 50,
            "children": [
              stmod.layout_dict,
              {
                "type": "tab",
                "id": "tab-sounding",
                "name": "sounding"
              },
              {
                "type": "tab",
                "id": "tab-tTEM",
                "name": "ttem"
              },
              
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
    ), 
    html.Div(id='output-click')
  ]
)

for panel in panels:
    panel.add_callbacks(app)

@app.callback(
    [ 
        Output('sounding', 'figure', allow_duplicate=True),
        Output('tTEM',     'figure', allow_duplicate=True),
        Output('model_graph', 'figure', allow_duplicate=True),
        Output('model_section', 'figure', allow_duplicate=True),
    ],
    [Input('map', 'relayoutData'), Input('map', 'selectedData')],
    prevent_initial_call="initial_duplicate",
    allow_duplicate=True
)
def handle_map_interactions(relayout_data, selected_data):
    """Handle both drawing and selection on the map"""
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    trigger_prop = ctx.triggered[0]['prop_id'].split('.')[1]
    
    selected_sites = []
    
    # Handle drawing interactions
    if trigger_prop == 'relayoutData' and relayout_data:
        # Check if shapes were drawn
        if 'shapes' in relayout_data:
            m1.drawn_shapes = relayout_data['shapes']
            selected_sites = m1.get_selected_sites()
        # Handle shape deletion
        elif any(key.startswith('shapes[') and key.endswith('].x0') for key in relayout_data.keys()):
            # Update shapes if they were modified
            shapes = []
            i = 0
            while f'shapes[{i}].x0' in relayout_data:
                shape = {
                    'type': relayout_data.get(f'shapes[{i}].type', 'rect'),
                    'x0': relayout_data.get(f'shapes[{i}].x0'),
                    'x1': relayout_data.get(f'shapes[{i}].x1'),
                    'y0': relayout_data.get(f'shapes[{i}].y0'),
                    'y1': relayout_data.get(f'shapes[{i}].y1'),
                }
                shapes.append(shape)
                i += 1
            m1.drawn_shapes = shapes
            selected_sites = m1.get_selected_sites()
    
    # Handle point selection
    elif trigger_prop == 'selectedData' and selected_data and 'points' in selected_data:
        selected_sites = [point['pointIndex'] for point in selected_data['points']]+[-1]
    
    # If no sites selected, don't update
    if not selected_sites:
        raise PreventUpdate
    
    # Update dataframes with selected sites
    new_df = df_res[df_res['site_id'].isin(selected_sites)]
    dbdt1.dataframe = new_df
    dbdt2.dataframe = new_df
    new_mod = df_mod[df_mod['site_id'].isin(selected_sites)]
    mod1.dataframe = new_mod 
    mod2.dataframe = new_mod
    
    return dbdt1.render(), dbdt2.render(), mod1.render(), mod2.render()


from dash import Input, Output, State, html, dcc, ctx

app.clientside_callback(
    """
        function(id) {
            document.addEventListener("keydown", function(event) {
                if (event.ctrlKey) {
                    if (event.key == 'd') {
                        document.getElementById('disableButton').click()
                        event.stopPropagation()
                    }
                    if (event.key == 'e') {
                        document.getElementById('enableButton').click()
                        event.stopPropagation()
                    }
                }
            });
            return window.dash_clientside.no_update       
        }
    """,
    Output("disableButton", "id"),
    Input("disableButton", "id")
)

@app.callback(
    [
        Output("output-click", "children"),
        Output("tTEM", "figure", allow_duplicate=True), Output("sounding", "figure", allow_duplicate=True)
     ],
    Input("disableButton", "n_clicks"),
    Input("enableButton", "n_clicks"),
    State("tTEM", "selectedData"),
    State("sounding", "selectedData"),
    prevent_initial_call=True,
    allow_duplicate=True,
)
def show_value(n1, n2, ttem_selected, sounding_selected):
    
    if str(ctx.triggered_id) == 'disableButton':
        inuse = False
    elif str(ctx.triggered_id) == 'enableButton':
        inuse = True

    if ttem_selected:
        data_ids = [point['customdata'][1] for point in ttem_selected['points'] if 'customdata' in point]
    elif sounding_selected:
        data_ids = [point['customdata'][1] for point in sounding_selected['points'] if 'customdata' in point]
    else:
        raise PreventUpdate
    
    df_res.loc[df_res['data_id'].isin(data_ids), 'inuse_manual'] = inuse
    df_res['include'] = calculate_inuse(df_res['inuse_auto'], df_res['inuse_manual'])
    dbdt1.dataframe = df_res[df_res['site_id'].isin(dbdt1.dataframe['site_id'].unique())]
    dbdt2.dataframe = df_res[df_res['site_id'].isin(dbdt2.dataframe['site_id'].unique())]

    return ctx.triggered_id, dbdt2.render(), dbdt1.render()

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
    
    return 'flex-layout'

@app.callback(
    Output('map', 'figure', allow_duplicate=True),
    [
        Input('model_section', 'hoverData'),
        Input('tTEM', 'hoverData'),
    ],
    prevent_initial_call="initial_duplicate",
    allow_duplicate=True
)
def cross_panel_hover(sounding_hover, ttem_hover):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    hover_data = ctx.triggered[0]['value']
    if not hover_data or 'points' not in hover_data:
        raise PreventUpdate
    if trigger_id == 'tTEM':
        x_value = hover_data['points'][0]['x']
        site_id = dbdt2.dataframe.query(f'{dbdt2.settings.x_axis} == @x_value')['site_id'].iloc[0]
        m1.highlighted = site_id
    elif trigger_id == 'model_section':
        x_value = hover_data['points'][0]['x']
        site_id = mod2.dataframe.query(f'{mod2.settings.x_axis} == @x_value')['site_id'].iloc[0]
        m1.highlighted = site_id

    return m1.render()

try:

    app.run(debug=True, port=8050, dev_tools_hot_reload=True)
except Exception as e:
    print(f"Error running app: {e}")
finally:
    print('App has stopped running.')

#start msedge --app=http://127.0.0.1:8050/

