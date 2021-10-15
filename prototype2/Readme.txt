Prerequisites:
	-Docker version 20 or later
Steps for running the prototype:
	- Command to build the prototype - (docker build -t 'container_name' .)  . Any container name can be used as long as it remains consistent with running the prototype.
	- Command for running the prototype - (docker run -it --mount type=bind,source="$(pwd)",target=/host --tmpfs /mnt/ramdisk -e "filename='filename'" -e "timeout='timeout'") capstone2. The recommended values for 'timeout' are 1,2 and 10 seconds for the easy, medium and hard problems respectively. The list of available filenames can be found at the end of the readme.
	- The output of the prototype is stored in "output.txt" the working directory that the docker was run from.
Output file format:
	- The output is contained in a text file named "output.txt". The text file has 1000 entries representing each run of carlsat which was made.
	- The format for each line is given by (previous,current,a,b,c,e,f,r,x,endscore,improvement,stucktime) which allows the client to track ancestry by reading through the endscore of each line choosing which endscore they want to use. Once they have chosen the endscore they can keep track of the parameters at each step while moving back using the value of previous until previous==0, which indicates that the client has reached the starting point.
Database creation:
	- The creation of the database takes place in prototype2.py along with permission commands
Common errors:
	- Unable to build docker because docker daemon denies permission. Solution sudo chmod 666 /var/run/docker.sock
	- The timeout environment variable must only contain numbers, i.e no white spaces, letters or symbols
	- The notation 'variable' is used to indicate a part of the command where the client must supply their choice of input. When doing so the ' ' symbol musn't be used.
Available problems:
	- test-30-10681.wcard, test-30-14971.wcard, test-30-26011.wcard, test-30-29086.wcard, test-30-29218.wcard, test-100-7902.wcard, test-100-10119.wcard, test-100-11503.wcard, test-100-14082.wcard, test-100-30439.wcard, test-500-14838.wcard, test-500-15790.wcard, test-500-24992.wcard, test-500-25645.wcard, test-500-26676.wcard
