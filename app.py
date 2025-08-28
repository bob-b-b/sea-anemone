from panels import *

from dash import dcc
from dash import Dash, callback_context
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from temframe import TEMframe

external_stylesheets = [dbc.themes.BOOTSTRAP]
app = Dash(__name__, suppress_callback_exceptions=True, assets_folder='assets',  external_stylesheets=external_stylesheets)
app.title = "sea anemone"

import os

global TABLES

# df_data = TEMframe.from_usf_folder('/home/matt/geophysics_data/TEM/sTEM_data/2025_0302/USF_Files_dawa river 3/')
df_data = TEMframe.from_usf_folder('C:/Users/au646858/Downloads/USF_Files_dawa river/')
import pandas

history = ['df_data = TEMframe.from_usf_folder("C:/Users/au646858/Downloads/USF_Files_dawa river/")',
 'df_mods, df_data2 = df_data.invert(res_start, max_iterations=20)']

# df_data = TEMframe(pandas.read_csv('dawa_river_data.csv'),   history=history)
# df_mods = TEMframe(pandas.read_csv('dawa_river_models.csv'), history=history)
df_overview = df_data.overview()


# df_data = None
df_mods = None
# df_overview = None


TABLES = {
    'data': df_data,
    'overview': df_overview,
    'models': df_mods
}




m1 = Map(data=df_overview)
dbdt1 = dbdtSounding(dataframe=df_data)
dbdt2 = dbdtSection(dataframe=df_data)

u1 = Upload()
t1 = Table(df_overview, id='table_overview')


mod1 = ModelGraph(   dataframe=df_mods )
mod2 = ModelSection( dataframe=df_mods )


x = html.Div([
      dcc.Markdown(children='### buttons and hot keys'),
      dbc.Button("disable [ctrl+d]", id='disableButton'),
      dbc.Button("enable  [ctrl+e]", id='enableButton'),
      dbc.Button("previous [<-]", id='highlight_prev'),
      dbc.Button("next [->]", id='highlight_next'),
    ]
, id='processing_buttons')


stmod = StartingModel.standard(rho=10.)

panels = [u1, m1, dbdt1, t1, dbdt2, mod1, mod2, stmod]
nodes = [node for panel in panels for node in panel.to_nodes()]+[dfl.Tab(id=f'tab-processing_buttons', children=[x]), dfl.Tab(id='tab-panel_list', children=[panel_list])]


config = {'global': {}, 
          'borders': [{'type': 'border', 'size': 200, 'location': 'left', 'children': [{'type': 'tab', 'id': 'tab-panel_list', 'name': 'Panels', 'component': 'text'}]}, {'type': 'border', 'selected': 0, 'size': 100, 'location': 'bottom', 'children': [{'type': 'tab', 'id': 'tab-processing_buttons', 'name': 'buttons'}]}], 'layout': {'type': 'column', 'id': '#862b2fc6-2ef4-4251-a485-e158ed2bf975', 'children': [{'type': 'row', 'id': '#f38c40d3-e354-4752-8bd8-0f924591ece9', 'children': [{'type': 'row', 'id': '#08653c5d-d61d-4327-b886-4f317211fdfe', 'weight': 32.81616953938199, 'children': [{'type': 'tabset', 'id': '#328817bb-4e54-448e-887f-00356fda1ff9', 'weight': 31.43338620142744, 'selected': 1, 'children': [{'type': 'tab', 'id': 'tab-map', 'name': 'map'}, {'type': 'tab', 'id': 'tab-upload', 'name': 'upload'}], 'active': True, 'maximized': True}, {'type': 'tabset', 'id': '#d8d4e938-96d7-478a-8393-66687d22af08', 'weight': 38.105784067666576, 'children': [{'type': 'tab', 'id': 'tab-sounding', 'name': 'sounding'}]}, {'type': 'tabset', 'id': '#7592b363-bc0a-4d12-a473-0a6659bb4f21', 'weight': 30.46082973090599, 'children': [{'type': 'tab', 'id': 'tab-starting_model', 'name': 'starting_model'}]}]}, {'type': 'tabset', 'id': '#66b4df30-1c51-4f0a-a07e-11450466c7b9', 'weight': 36.79929156680697, 'children': [{'type': 'tab', 'id': 'tab-tTEM', 'name': 'ttem'}]}, {'type': 'tabset', 'id': '#b0c1f8d2-3e4a-4c5b-9f6d-7e8f9a0b1c2d', 'weight': 30.384538893811026, 'children': [{'type': 'tab', 'id': 'tab-model_section', 'name': 'model section'}]}]}]}}

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

    df_data = TABLES['data']
    df_mods = TABLES['models']

    # Update dataframes with selected sites
    new_df = df_data[df_data['site_id'].isin(selected_sites)]
    dbdt1.dataframe = new_df
    dbdt2.dataframe = new_df
    new_mod = df_mods[df_mods['site_id'].isin(selected_sites)]
    mod1.highlighted = None
    mod1.dataframe = new_mod 
    mod2.dataframe = new_mod

    
    return dbdt1.render(), dbdt2.render(), mod1.render(), mod2.render()


from dash import Input, Output, State, html, dcc, ctx

app.clientside_callback(
    """
        function(id) {
            document.addEventListener("keydown", function(event) {
                // Check if focus is on an input element
                const activeElement = document.activeElement;
                const isInputFocused = activeElement && (
                    activeElement.tagName === 'INPUT' || 
                    activeElement.tagName === 'TEXTAREA' || 
                    activeElement.contentEditable === 'true'
                );
                
                if (event.ctrlKey) {
                    if (event.key == 'd') {
                        document.getElementById('disableButton').click()
                        event.preventDefault()
                        event.stopPropagation()
                    }
                    if (event.key == 'e') {
                        document.getElementById('enableButton').click()
                        event.preventDefault()
                        event.stopPropagation()
                    }
                }
                
                // Arrow keys without Ctrl, but only if not typing in an input
                if (!isInputFocused) {
                    if (event.key == 'left') {
                        document.getElementById('highlight_prev').click()
                        event.preventDefault()
                        event.stopPropagation()
                    }
                    if (event.key == 'right') {
                        document.getElementById('highlight_next').click()
                        event.preventDefault()
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
    df_data = TABLES['data']
    
    df_data.loc[df_data['data_id'].isin(data_ids), 'inuse_manual'] = inuse
    df_data['include'] = df_data['inuse_manual'].fillna(df_data['inuse_auto'])
    dbdt1.dataframe = df_data[df_data['site_id'].isin(dbdt1.dataframe['site_id'].unique())]
    dbdt2.dataframe = df_data[df_data['site_id'].isin(dbdt2.dataframe['site_id'].unique())]

    return ctx.triggered_id, dbdt2.render(), dbdt1.render()

@app.callback(
    [
        Output("output-click", "children", allow_duplicate=True),
        Output('map', 'figure', allow_duplicate=True),
        Output('model_graph', 'figure', allow_duplicate=True),
        Output('sounding', 'figure', allow_duplicate=True)],
    Input('highlight_prev', 'n_clicks'),
    Input('highlight_next', 'n_clicks'),
    prevent_initial_call=True,
    allow_duplicate=True
)
def highlight_change(n1, n2):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    highlighted = m1.highlighted
    if trigger_id == 'highlight_prev':
        highlight_change = -1
    elif trigger_id == 'highlight_next':
        highlight_change = 1
    if highlighted is None:
        highlighted = 0
    else:
        highlighted += highlight_change
    m1.highlighted = highlighted
    mod1.highlighted = highlighted
    dbdt1.dataframe = df_data[df_data['site_id'] == highlighted]

    return ctx.triggered_id, m1.render(), mod1.render(), dbdt1.render()

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

@app.callback(
    Output('map', 'figure', allow_duplicate=True),
    Output('model_graph', 'figure', allow_duplicate=True),
    Output('sounding', 'figure', allow_duplicate=True),
    [
        Input('model_section', 'clickData'),
        Input('tTEM', 'clickData'),
        Input('map', 'clickData')
    ],
    prevent_initial_call="initial_duplicate",
    allow_duplicate=True
)
def cross_panel_click(model_click, ttem_click, map_click):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    click_data = ctx.triggered[0]['value']
    if not click_data or 'points' not in click_data:
        raise PreventUpdate
    if trigger_id == 'tTEM':
        x_value = click_data['points'][0]['x']
        site_id = dbdt2.dataframe.query(f'{dbdt2.settings.x_axis} == @x_value')['site_id'].iloc[0]
    elif trigger_id == 'model_section':
        x_value = click_data['points'][0]['x']
        site_id = mod2.dataframe.query(f'{mod2.settings.x_axis} == @x_value')['site_id'].iloc[0]
    elif trigger_id == 'map':
        site_id = int(click_data['points'][0]['pointNumber'])
    else:
        site_id = None
  
    m1.highlighted = site_id
    mod1.highlighted = site_id
    dbdt1.dataframe = df_data[df_data['site_id'] == site_id]

    return m1.render(), mod1.render(), dbdt1.render()



@app.callback(
    [Output('starting_model', 'figure', allow_duplicate=True),
     Output('model_section', 'figure', allow_duplicate=True),
     Output('model_graph', 'figure', allow_duplicate=True),
     Output('tTEM', 'figure', allow_duplicate=True),
     Output('sounding', 'figure', allow_duplicate=True)],
    Input('invert_all_button', 'n_clicks'),
    prevent_initial_call=True
)
def launch_inversion(n_clicks):
    if n_clicks:
        from torch import from_numpy
        rho = from_numpy(stmod.dataframe['resistivity'].values)
        z   = from_numpy(stmod.dataframe['depth'].values[:-1])

        res_start                        = LogResistivity.smooth(rho,z) 
        TABLES['models'], TABLES['data'] = TABLES['data'].invert(res_start)
        mod1.dataframe                   = TABLES['models']
        mod2.dataframe                   = TABLES['models']
        dbdt1.dataframe                  = TABLES['data']
        dbdt2.dataframe                  = TABLES['data']
    return stmod.misfit_render(), mod2.render(), mod1.render(), dbdt2.render(), dbdt1.render()

@app.callback(
    [Output('output-data-upload', 'children'),
     Output('map', 'figure', allow_duplicate=True),
     Output('sounding', 'figure', allow_duplicate=True),
     Output('tTEM', 'figure', allow_duplicate=True),
     Output('model_graph', 'figure', allow_duplicate=True),
     Output('model_section', 'figure', allow_duplicate=True)
    ],
    Input('upload-data', 'contents'),
    prevent_initial_call=True
)
def upload_file(contents):
    if contents is None:
        raise PreventUpdate
    
    TABLES['data']            = TEMframe.from_zip(contents[0])
    TABLES['data'].history    = ['df_data = TEMframe.from_zip("uploaded_data_zip.txt")']
    TABLES['data']['include'] = TABLES['data']['inuse_manual'].fillna(TABLES['data']['inuse_auto'])
    TABLES['overview']        = TABLES['data'].overview()
    TABLES['models']          = None

    dbdt1.dataframe = TABLES['data'].copy()
    dbdt2.dataframe = TABLES['data'].copy()
    m1.dataframe    = TABLES['overview']
    mod1.dataframe  = TABLES['models']
    mod2.dataframe  = TABLES['models']


    return html.Div("File uploaded successfully."), m1.render(), dbdt1.render(), dbdt2.render(), mod1.render(), mod2.render()

@app.callback(
    Output('map', 'figure', allow_duplicate=True),
    Input('flex-layout', 'model'),
    prevent_initial_call=True

)
def print_flex_layout_model(model):
    print(f"Flex layout model: {model}")
    return m1.render()

try:

    app.run(port=8050, debug=True, dev_tools_hot_reload=True)
except Exception as e:
    print(f"Error running app: {e}")
finally:
    print('App has stopped running.')

#start msedge --app=http://127.0.0.1:8050/

