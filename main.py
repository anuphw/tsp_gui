import os
from os.path import join, dirname, realpath, basename
from os import listdir
import pandas as pd
import webbrowser
import textwrap
# From solver actualData.py
from http import client
import pandas as pd
import random
import time
import json
from ortools.sat.python import cp_model
import math
from onemapsg import OneMapClient
import sqlite3
from datetime import datetime
from time import sleep

L = 100
client = OneMapClient("anuphw@gmail.com","Ichalkaranji!123")

places = None
distances = None

import PySimpleGUI as sg
sg.theme("DarkTeal2")

def getCoords(postal_code,db='database.sqlite3'):
    conn = sqlite3.connect('database.sqlite3')
    global client, places
    postal_code = '{0:0>6}'.format(postal_code)
    if not conn:
        try:
            conn = sqlite3.connect(db)
        except:
            print("Could not connect to ",db)
            return
    if type(places) != type(pd.DataFrame()):
        places = pd.read_sql_query('select * from places',conn)
        #print(places)
    if len(places[places['postal_code'] == postal_code])>0:
        return places[places['postal_code'] == postal_code]['latitude'].values[0],places[places['postal_code'] == postal_code]['longitude'].values[0]
    else:
        #print(f"getting coordinates for {postal_code}")
        x = client.search('Singapore '+str(postal_code))
        time.sleep(0.4)
        if x['found']> 0:
            cur = conn.cursor()
            cur.executemany("insert or ignore into places (postal_code,blk_no, road_name, x, y, latitude,longitude) values (?,?,?,?,?,?,?)"
            ,[[x['results'][0]['POSTAL']
            ,x['results'][0]['BLK_NO']
            ,x['results'][0]['ROAD_NAME']
            ,x['results'][0]['X']
            ,x['results'][0]['Y']
            ,x['results'][0]['LATITUDE']
            ,x['results'][0]['LONGITUDE']]])
            conn.commit()
            cur.close()
            return [x['results'][0]['LATITUDE'],x['results'][0]['LONGITUDE']]
    if conn:
        conn.commit()
        conn.close()
    return None


def getNDeliveries(inp):
    df = pd.read_csv(inp,header=0)
    source = []
    destination = []
    weights = []
    for s in df['source']:
        source.append('{0:0>6}'.format(s))
    for d in df['destination']:
        destination.append('{0:0>6}'.format(d))
    for w in df['wgt']:
        weights.append(w)
    source_address = source
    destination_address = destination
    if 'source_address' in df.columns:
        source_address = list(df['source_address'].values)
    if 'destination_address' in df.columns:
        destination_address = list(df['destination_address'].values)
    return source, destination, weights, source_address, destination_address

def distance(pin1,pin2,db='database.sqlite3'):
    pin1 = '{0:0>6}'.format(pin1)
    pin2 = '{0:0>6}'.format(pin2)
    if pin1 == pin2:
        return 0
    #print(f"pin1 = {pin1} and pin2 = {pin2}")
    conn = sqlite3.connect('database.sqlite3')
    global client, distances
    if not conn:
        try:
            conn = sqlite3.connect(db)
        except:
            print("Could not connect to ",db)
            return
    if type(distances) != type(pd.DataFrame()):
        distances = pd.read_sql_query('select * from distances',conn)
    distances['postal_code_1'] = distances['postal_code_1'].apply(lambda x: '{0:0>6}'.format(x))
    distances['postal_code_2'] = distances['postal_code_2'].apply(lambda x: '{0:0>6}'.format(x))
    if len(distances[(distances['postal_code_1'] == pin1) & (distances['postal_code_2'] == pin2)]) > 0:
        if conn:
            conn.commit()
            conn.close()
        return distances[(distances['postal_code_1'] == pin1) & (distances['postal_code_1'] == pin1)]['distance'].values[0]
    else:
        a = getCoords(pin1)
        b = getCoords(pin2)
        #print(f"getting distance between {pin1} and {pin2}")
        route = client.get_route(a,b,'drive')
        while not route:
            #print(f'refreshing token in route {a} n {b}')
            time.sleep(0.5)
            client.check_expired_and_refresh_token()
            route = client.get_route(a,b,'drive')
        if route:
            cur = conn.cursor()
            cur.executemany('insert or ignore into distances (postal_code_1,postal_code_2,distance,timeToReach,update_dt) values (?,?,?,?,?)',
            [[pin1, pin2,route['route_summary']['total_distance'],route['route_summary']['total_time'],datetime.now().strftime("%Y-%m-%d")]])
            conn.commit()
            cur.close()
            return int(route['route_summary']['total_distance'])
        if conn:
            conn.commit()
            conn.close()
        return None

def distance_matrix(start, source_destination):
    sd = source_destination + [start]
    from_eachother = [[distance(a,b) for a in sd] for b in sd]
    #print(from_eachother)
    return from_eachother

def showReq(source, destination):
    for i in range(len(source)):
        s = source[i]
        d = destination[i]
        plt.arrow(s[0],s[1],d[0]-s[0],d[1]-s[1])
    plt.show()

def showPath(path,origin="348745",inp="./input.csv"):
    df= pd.read_csv(inp,header=0)
    url = f"https://www.google.com/maps/dir/Singapore%20{origin}"
    i = len(path)-1
    df['source'] = df['source'].apply(lambda x: '{0:0>6}'.format(x))
    df['destination'] = df['destination'].apply(lambda x: '{0:0>6}'.format(x))
    while True:
        for j in range(len(path)):
            if path[i][j] == 1:
                i = j
                break
        if i == len(path)-1:
            return url+f'/Singapore%20{origin}'
        if (i < len(df)):
            url += f'/Singapore%20{df.loc[i,"source"]}'
            #print(i,url)
        else:
            url += f'/Singapore%20{df.loc[i-len(df),"destination"]}' 
            #print(i,url)
    print(url)
    return url


def TSP(input_file,truck_capacity = 360):
    df = pd.read_csv(input_file)
    continu = True
    for c in ['source','destination','wgt']:
        continu &= (c in df.columns)
    if not continu:
        return False, "Invalid input", []
    # Integer Programming Formulation of Traveling Salesman Problems 
    source, dest, wgt, source_address, destination_address = getNDeliveries(input_file)
    wgt += [-w for w in wgt]
    stops = source + dest
    origin = "348745"
    distmat = distance_matrix(origin,stops)
    # for i in distmat:
    #     print(i)
    num_constraints = 0
    n_dest = len(dest)
    num_stops = len(distmat)
    model = cp_model.CpModel()
    # alpha[i][j] = 1 if we go from i -> j directly
    alpha = [ [ model.NewBoolVar('alpha_%i_%i' % (stop1, stop2)) for stop2 in range(num_stops)] for stop1 in range(num_stops)]
    # U_i's from the paper
    u = [ model.NewIntVar(1,num_stops,'u_%i' % (i)) for i in range(num_stops)]
    # beta[i][j] = 1 if u[i] <= j+1. This is added to make sure that truck load is less than capacity
    beta = [ [ model.NewBoolVar('beta_%i_%i' % (i,j)) for i in range(num_stops-1)] for j in range(num_stops-1) ]
    # Unique edge in and out of a destination
    for i in range(num_stops):
        model.Add(sum(alpha[i][j] for j in range(num_stops) if i!=j) == 1) # uniq edge out of i
        model.Add(sum(alpha[j][i] for j in range(num_stops) if i!=j) == 1) # uniq edge into i
    # beta[i][j] = 1 if u[i] <= j+1. This is added to make sure that truck load is less than capacity
    for i in range(num_stops-1):
        for j in range(num_stops-1):
            model.Add(u[i]<=j+1).OnlyEnforceIf(beta[i][j])
            model.Add(u[i]>j+1).OnlyEnforceIf(beta[i][j].Not())
    # The magic constraint from the paper
    for i in range(num_stops-1):
        for j in range(num_stops-1):
            if i != j:
                model.Add(u[i]-u[j]+alpha[i][j]*num_stops <= num_stops-1)
    # pick up is done before drop off
    for i in range(int(n_dest)):
        model.Add(u[i] < u[i+n_dest])
    # The truck load at any point in time is less than it's capacity
    for i in range(int(num_stops-1)):
        model.Add(sum(wgt[j]*beta[j][i] for j in range(num_stops-1)) <= truck_capacity)   
    # Total distance travelled (Can also be changed to total time required in function distance())
    objective = model.NewIntVar(0, 10000000000, 'objective')
    model.Add(sum(distmat[i][j]*alpha[i][j] for i in range(num_stops) for j in range(num_stops) if i != j) == objective)
    model.Minimize(objective)
    path = [[0 for _ in range(num_stops)] for _ in range(num_stops)]
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    if status == cp_model.OPTIMAL:
        for i in range(num_stops):
            for j in range(num_stops):
                path[i][j] = solver.Value(alpha[i][j])
                #print(path[i][j],end=" ")
            #print("")
        uarr = [0 for _ in range(num_stops-1)]
        for i in range(n_dest):
            uarr[i] = solver.Value(u[i])
            uarr[i+n_dest] = solver.Value(u[i+n_dest])
        truck_load = 0
        loc_no = 0
        pick_drops = []
        print(uarr[i])
        for i in range(num_stops-1):
            loc_no += 1
            for j in range(num_stops-1):
                if uarr[j] == loc_no:
                    truck_load += wgt[j]
                    if j < n_dest:
                        #pick_drops.append({'action':'Pick','address':source_address[j],'orderNo':(j+1),'weight':wgt[j],'truck_load':truck_load})
                        pick_drops.append([j+1,source_address[j],'Pick',wgt[j],truck_load])
                        #pick_drops.append(f"Pick up {wgt[j]} at {source_address[j]} for order number {j+1}. Truck Load {truck_load}")
                        #print(f"Pick up {wgt[j]} at {source_address[j]} for order number {j+1}. Truck Load {truck_load}")
                    else:
                        #pick_drops.append({'action':'Drop','address':destination_address[j-n_dest],'orderNo':(j-n_dest+1),'weight':wgt[j-n_dest],'truck_load':truck_load})
                        pick_drops.append([j-n_dest+1,destination_address[j-n_dest],'Drop',wgt[j-n_dest],truck_load])
                        #pick_drops.append(f"Dropoff {-wgt[j]} at {destination_address[j-n_dest]} for order number {j-n_dest+1}. Truck Load {truck_load}")
                        #print(f"Dropoff {-wgt[j]} at {destination_address[j-n_dest]} for order number {j-n_dest+1}. Truck Load {truck_load}")
                    break
    path = showPath(path,inp = input_file)
    return True, path, pick_drops




# app = Flask(__name__)
# scheduler = APScheduler()
# CORS(app)

# cors = CORS(app, resource={
#     r"/*":{
#         "origins":"*"
#     }
# })

# enable debugging mode
# app.config["DEBUG"] = True

# UPLOAD_FOLDER = 'static/files'
# app.config['UPLOAD_FOLDER'] =  UPLOAD_FOLDER

# @app.after_request
# def add_header(r):
#     """
#     Add headers to both force latest IE rendering engine or Chrome Frame,
#     and also to cache the rendered page for 10 minutes.
#     """
#     r.headers["Pragma"] = "no-cache"
#     r.headers["Expires"] = "0"
#     r.headers['Cache-Control'] = 'public, max-age=0, no-cache, no-store, must-revalidate'
#     return r

# @app.route('/')
# def index():
#     return render_template('index.html')

# # Root URL
# @app.route('/upload')
# def upload():
#      # Set The upload HTML template '\templates\index.html'
#     return render_template('upload.html')


# # Get the uploaded files
# @app.route("/upload", methods=['POST'])
# def uploadFiles():
#       # get the uploaded file
#       uploaded_file = request.files['file']
#       if uploaded_file.filename != '':
#            file_path = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename)
#           # set the file path
#            uploaded_file.save(file_path)
#           # save the file
#       return redirect(url_for('index'))

# @app.route("/list")
# def listFiles():
#     inpFiles = find_filenames(UPLOAD_FOLDER,'.csv')
#     outFiles = find_filenames(OUTFOLDER,'.json')
#     out = dict()
#     for inp in inpFiles:
#         out[inp] = dict()
#         if os.path.exists(os.path.join(OUTFOLDER,inp+'.json')):
#             with open(os.path.join(OUTFOLDER,inp+'.json'),'r') as f:
#                 out[inp] = json.load(f)
#         else:
#             out[inp] = {"success": False, "path": "Finding best route", "pick_drops": []}
#     return render_template('list.html',out_files=out)

# @app.route('/files', defaults={'req_path': ''})
# @app.route('/files/<path:req_path>')
# def dir_listing(req_path):
#     BASE_DIR = '.'

#     # Joining the base and the requested path
#     abs_path = os.path.join(BASE_DIR, req_path)

#     # Return 404 if path doesn't exist
#     if not os.path.exists(abs_path):
#         return abort(404)

#     # Check if path is a file and serve
#     if os.path.isfile(abs_path):
#         return send_file(abs_path)

#     # Show directory contents
#     files = os.listdir(abs_path)
#     return render_template('files.html', files=files)

# def find_filenames( path_to_dir, suffix=".csv" ):
#     filenames = listdir(path_to_dir)
#     return [ filename for filename in filenames if filename.endswith( suffix ) ]

# OUTFOLDER = 'static/output'
# def scheduledTask():
#     inpFiles = find_filenames(UPLOAD_FOLDER,'.csv')
#     outFiles = find_filenames(OUTFOLDER,'.json')
#     for inpf in inpFiles:
#         if (inpf+'.json') not in outFiles:
#             success, path, pick_drops = TSP(os.path.join(UPLOAD_FOLDER,inpf))
#             out = dict()
#             out['success'] = success
#             out['path'] = path
#             out['pick_drops'] = pick_drops
#             with open(os.path.join(OUTFOLDER,inpf+'.json'),'w') as f:
#                 f.write(json.dumps(out))

path, pick_drops = None, None
pick_drops_header = ['Order#','Address','Action','Weight','Truck Load']


layout = [[sg.T("")], 
    [sg.Text("Choose a file: "), sg.Input(), sg.FileBrowse(key="-input-")],
    [sg.Text("Truck Capacity (#cartons): "), sg.Input(default_text="360",key='-truck-capacity-')],
    [sg.Button("Submit")],
    [sg.Button("View on Google Maps",visible=False,key='-google-')],
    [sg.Table(values=[[]],headings=pick_drops_header,
        auto_size_columns=True,justification='right',visible=False,key='-actions-',size=(100,None))],
    [sg.Button("Export",key='-export-',visible=False)]
    ]

window = sg.Window('Window Title', layout)


if __name__ == '__main__':
    while True:
        event, values = window.read(timeout=10)
        if event == sg.WIN_CLOSED or event=="Exit":
            break
        elif event == '-google-':
            if path:
                webbrowser.open(path)
        elif event == "Submit":
            print(values['-input-'])
            _, path, pick_drops = TSP(values['-input-'],int(values['-truck-capacity-']))
            window['-google-'].update(visible=True)
            window['-actions-'].update(values=pick_drops)
            window['-actions-'].update(visible=True)
            window['-export-'].update(visible=True)
            # window['-output-'].update(path+'\n'+'\n'.join([' '.join(y) for y in pick_drops]))
            print(path,pick_drops)
        elif event == '-export-':
            folder_name = sg.popup_get_folder("Choose folder to export actions table")
            pickDrops  = pd.DataFrame(pick_drops,columns=pick_drops_header)
            pickDrops.to_csv(os.path.join(folder_name,'output.csv'),index=None)
            print(folder_name)



    # job = scheduler.add_job(id='job_id',func=scheduledTask,trigger='interval',minutes=2)
    # job.modify(max_instances=1)
    # scheduler.start()
    # app.run(port=8080)
