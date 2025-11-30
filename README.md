# IntelliGEN
## Overview

Intelligen is an automated UAV test-generation system designed to create high-quality, failure-revealing test cases. It works by first generating a  pool of seed configurations, each defining obstacle placements and environment parameters. These seeds are then evaluated through simulation, and Intelligen automatically identifies and selects the most effective seeds, i.e., those that are most likely to induce collisions, near-misses, or risky behaviors in the UAV.

By combining automated seed generation with intelligent seed selection, Intelligen builds a focused set of high-impact UAV test cases that expose weaknesses in autonomy and improve the overall robustness of UAV systems.

## Installation and Usage


1. Clone the repository: 
    ```bash
    git clone https://github.com/arham83/Intelligent-UAV-Gen.git 
	```

2. Navigate to the snippets folder:
    ```bash
    cd Intelligent-UAV-Gen/snippets
    ```

3. Create a Docker Image:
	```bash
    sudo docker build -t [YOUR_IMAGE_NAME] .
    ```

4. Setting .env file:
	```bash
    cd ..
	vim .env
    ```
	```plaintext
	# .env file

	# Add your ChatGPT API key here
	OPENAI_API_KEY=YOUR_API_KEY
	
	#Change your ChatGPT model
	MODEL_NAME=gpt-4o-mini

5. Run the Docker container:
	```bash
    sudo docker run --env-file .env -dit [YOUR_IMAGE_NAME]

	sudo docker exec -it [CONTAINER_ID] bash
    ```
	
6. Run the generator:
	```bash
    python3 cli.py generate [PATH_TO_MISSION_YAML] [BUDGET]
    ```

## Author

- Arham Riaz
  - Email: arham.riaz@mbzuai.ac.ae
  - Affiliation: MBZUAI - Mohamed bin Zayed University of Artificial Intelligence

- Taohong Zhu
  - Email: taohong.zhu@postgrad.manchester.ac.uk
  - Affiliation: The University of Manchester

- Youcheng Sun
  - Email: youcheng.sun@mbzuai.ac.ae
  - Affiliation: MBZUAI - Mohamed bin Zayed University of Artificial Intelligence

