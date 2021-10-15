import sys
import os
import random
import threading
import subprocess
import mysql.connector
import numpy as np
from pymoo.algorithms.soo.nonconvex.de import DE
from pymoo.optimize import minimize
from pymoo.factory import get_sampling
from multiprocessing.pool import ThreadPool
from pymoo.core.problem import starmap_parallelized_eval
from pymoo.core.problem import ElementwiseProblem
from threading import *

#Defining problem class
class BestScore(ElementwiseProblem):
    global end_scores                                                              #Indicates to the class to use the global variables under these names rather than creating local versions, they need to be global so that the DE algorithm can sample from them outside of the class
    global improvement
    global stuck_time
    global threadid
    
    def __init__(self, **kwargs):                                                  #initialises the class
        super().__init__(n_var=10,n_obj=1,n_constr=0,xl=0,xu=19,**kwargs)
    
    def _evaluate(self,x, out,*args, **kwargs):                                    #Defines how the class calculates the value of the objective based on the samples that the DE algorithm inputs
        if (end_scores[x[7]]+improvement[x[8]]+stuck_time[x[9]]==0):               #first generation run of carlsat, implies no previous saved states
            myresult = []
            lock.acquire()
            identity = self.getID(threadid)                                         
            lock.release()
            cost, score_improvement, stuck = self.parseOutput(identity, "", x, myresult)     
            self.makeDatabaseEntry(0, identity, cost, score_improvement, stuck, x)
            self.completedGenerationUpdate(identity)
            out["F"] = [cost]
        else:                                                                      #Used by threads in any generation excluding the first
            lock.acquire()
            mycursor.execute("SELECT current, endscore, improvement, stucktime FROM states") #We now have past saved states that we need to use to find the closest state
            myresult = mycursor.fetchall()
            identity = self.getID(threadid)
            lock.release()
            closest_matching_state_file = self.calculateClosestState(x, myresult)
            closest_state = "./mnt/ramdisk/state"+str(closest_matching_state_file)+".out"
            cost, score_improvement, stuck = self.parseOutput(identity, closest_state, x, myresult) 
            self.makeDatabaseEntry(closest_matching_state_file, identity, cost, score_improvement, stuck, x)
            self.completedGenerationUpdate(identity)
            out["F"] = [cost]
    
    ##get counter of thread, we increment first since we initialise threadid=0
    def getID(self, threadid):
        threadid+=1
        identity = threadid
        return identity
    
    ##Runs CarlSAT with chosen parameters and parses the output of CarlSAT for the required values
    def parseOutput(self, identity, previous, x, myresult):            
        statefilename = "./mnt/ramdisk/state"+str(identity)+".out" 
        if (previous == ""):                                                 #Indicates that the thread is first generation - no previous saved states to use for -i parameter
            path = f"./CarlSAT -a {parameter_a[x[0]]} -b {parameter_b[x[1]]} -c {parameter_c[x[2]]} -e {parameter_e[x[3]]} -f {parameter_f[x[4]]} -r {parameter_r[x[5]]} -x {parameter_x[x[6]]} -m {solver_runtime/20} -v 2 -z {wcard_name} -w {statefilename}"       #The path variable is a formatted string representing what the terminal command would be to run CarlSAT with the parameters chosen by the DE algorithm.
        else:
            path = f"./CarlSAT -a {parameter_a[x[0]]} -b {parameter_b[x[1]]} -c {parameter_c[x[2]]} -e {parameter_e[x[3]]} -f {parameter_f[x[4]]} -r {parameter_r[x[5]]} -x {parameter_x[x[6]]} -m {solver_runtime/20} -v 2 -z {wcard_name} -i {previous} -w {statefilename}"
        result = subprocess.Popen(path, stdout=subprocess.PIPE,shell=True)   #We return the output of CarlSAT to the thread along with the state file to ensure thread safety
        output = result.communicate()[0].splitlines()
        cost =0
        score_improvement =0
        stuck =solver_runtime/20
        for i in range(len(output)-1,-1,-1):                                 #We filter through the output - which has a standard format - to find the values for cost and stuck
            line = str(output[i])
            if (line.find("after") != -1):
                temp = line[line.find(")")+5::]
                cost = int(temp[0:temp.find(" ")].replace(",",""))
                break
            elif (line.find("Time")!=-1):
                temp = line[line.find(":")+2::]
                timetaken = float(temp[0:temp.find(" ")])*1000
                stuck-=timetaken
        if (identity > 50):                                                  #We can only calculate score improvement if there is a previous saved state
        	score_improvement = myresult[j][1] - cost
        return cost, score_improvement, stuck
        
    def makeDatabaseEntry(self, previous, identity, cost, score_improvement, stuck, x):
        val = (previous, identity, parameter_a[x[0]], parameter_b[x[1]], parameter_c[x[2]], parameter_e[x[3]], parameter_f[x[4]], parameter_r[x[5]], parameter_x[x[6]],cost,score_improvement,stuck)
        lock.acquire()
        mycursor.execute(sql,val)                                            #Parameterised entry into database to prevent SQL injection vulnerabilities
        ancestrydb.commit()
        lock.release()
        
    def completedGenerationUpdate(self, identity):
        if (identity%50==0):
            min_valid=[100000000,100000000,100000000]                         #We want to represent the range of values that the next generation has to choose from for cost, stucktime and improvement in score
            max_valid=[0,0,0]
            for k in range(0,len(myresult),1):
                min_valid[0] = min(min_valid[0],myresult[k][1])              #The range is found by looking at all previous entries in the database and finding the max and min for each parameter
                min_valid[1] = min(min_valid[1],myresult[k][2])
                min_valid[2] = min(min_valid[2],myresult[k][3])
                max_valid[0] = max(max_valid[0],myresult[k][1])
                max_valid[1] = max(max_valid[1],myresult[k][2])
                max_valid[2] = max(max_valid[2],myresult[k][3])
            end_scores = ([random.choice(range(min_valid[0],max_valid[0]+1)) for t in range(20)])            #Once we have our range we choose 20 values within that range
            improvement = ([random.choice(range(min_valid[1],max_valid[1]+1)) for u in range(20)])
            stuck_time = ([random.choice(range(min_valid[2],max_valid[2]+1)) for v in range(20)])
            end_scores.sort()                                                #We then sort our arrays to maintain consistency with our DE choosing values from 1->20 mapping to our arrays which have values min->max
            improvement.sort()
            stuck_time.sort()
            
    def calculateClosestState(self, x, myresult):
        number_of_previous_generations=0
        excess = 0       #Needed as we decrement from the threads identity to the closest x: x%50==0 . We want to find x since we don't want a thread in our current generation to choose another thread from its generation as the closest state
        while(True):
            if (myresult[len(myresult)-1-excess][0] % 50 ==0):
                number_of_previous_generations = (len(myresult)-excess)//50
                break
            excess+=1
        closest_matching_state_file =0
        min_D = 100000000
        for j in range(0,number_of_previous_generations*50,1):
            D = ((end_scores[x[7]]-myresult[j][1])**2)+((improvement[x[8]]-myresult[j][2])**2)+(((stuck_time[x[9]]-myresult[j][3])**2)*0.5)   #The least squares algorithm used to find closest state
            min_D = min(min_D,D)
            if (D == min_D):
                closest_matching_state_file =j+1             #Our array index(j) and state identity are off by one since the array goes 0->len-1 while the state identites are 1->len
        return closest_matching_state_file
         

############### functions

## starting mysql server and fixing permissions

def startServer():
    os.system("service mysql start")
    os.system("mysql -u root -e 'USE mysql;'")
    query = "\"UPDATE mysql.user SET plugin='mysql_native_password' WHERE USER='root';\""
    os.system("mysql -u root -e "+query)
    os.system("mysql -u root -e 'FLUSH privileges;'")
    os.system("service mysql restart")

## reading in arguments
def readEnvironmentalVariables():
    wcard_name = os.getenv('filename')
    solver_runtime = int(os.getenv('timeout'))*1000
    return wcard_name, solver_runtime

## creating database
def createDatabase():
    mydb = mysql.connector.connect(host="localhost",user="root",password="")
    mycursor = mydb.cursor()
    mycursor.execute("CREATE DATABASE ancestrydb")
    mydb.close()
    ancestrydb = mysql.connector.connect(host="localhost",user="root",password="",database="ancestrydb")
    mycursor = ancestrydb.cursor()
    mycursor.execute("CREATE TABLE states (previous INT, current INT, a INT, b INT, c INT, e INT, f INT, r INT, x INT, endscore INT, improvement INT, stucktime INT)")
    sql = "INSERT INTO states (previous, current, a, b, c, e, f, r, x, endscore, improvement, stucktime) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    return ancestrydb, mycursor, sql

##parallelization
def threadCreation():
    n_threads= 6
    pool = ThreadPool(n_threads)
    threadid =0
    return pool, threadid
    
################### Running program

lock = Semaphore(1)

#valid parameters stored in arrays (in order they need to be supplied)

parameter_a = [1,2,5, 12, 17, 25, 50, 100,113, 125, 150, 200, 300, 400, 500, 600, 700, 800, 900, 1000]     #values are chosen to be "random" while also covering the valid sample space as evenly as possible
parameter_b = [1,2,3,5,10,12,25,50,100,125,150,200,300,400,500,600,700,800,900,1000]
parameter_c =[10,50,100,500,1000,3000,7000,10000,25000,50000,100000,200000,300000,400000,500000,600000,700000,800000,900000,1000000]
parameter_e = [0.1,0.5,1,2,5,10,25,50,75,100,150,200,300,400,500,600,700,800,900,1000]
parameter_f = [0.1,0.2,0.5,0.75,1,5,10,25,50,100,150,200,300,400,500,600,700,800,900,1000]
parameter_r = [0,1,2,3,5,10,12,15,20,25,30,40,50,60,70,75,80,90,95,100]
parameter_x = [1,2,5,10,50,100,150,250,500,750,1000,2000,3000,4000,5000,6000,7000,8000,9000,10000]
end_scores = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
improvement = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
stuck_time = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
startServer()
wcard_name, solver_runtime= readEnvironmentalVariables()
ancestrydb, mycursor, sql = createDatabase()
pool, threadid = threadCreation()
problem = BestScore(runner=pool.starmap, func_eval=starmap_parallelized_eval)      #initialises the class which describes the problem we are trying to optimize
algorithm = DE(pop_size=50,sampling=get_sampling("int_random"))                    #initialises Differential Evolution algorithm with 50 horizontal runs. DE was used as our problem has been defined with one objective
res = minimize(problem,algorithm,("n_gen",20),verbose=True,seed=1)                 #Begins the optimization process over 20 generations of 50 horizontal runs
mycursor.execute("SELECT * FROM states")                                           #After the optimization process is complete we output our whole database to a text file which is to be copied out of the docker container so that we can use the ancestry to repeat the steps taken to produce the best score
myresult = mycursor.fetchall()
text_file = open("/host/output.txt","w")                                           
for row in myresult:
    text_file.write(str(row))
    text_file.write("\n")
text_file.close()
mycursor.execute("DROP DATABASE ancestrydb")                                       #Once we've created the text file we no longer need the database
mycursor.close()
ancestrydb.close()

    


