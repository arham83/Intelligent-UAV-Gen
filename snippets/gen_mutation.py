import os

import yaml
from bot.prompter import Prompter
from utils.helper import Helper
from test_validator import TestValidator
from bot.sys_prompts.mutate_config import SYSTEM_PROMPT


class GenerateMutation:
    def __init__(self,logger, case_study, soi):
        """
        base_config_file -> will be used to write the base yaml file
        base_trajectory_path - > defines the base trajectory that UAV will follow 
        """
        self.logger = logger
        self.soi = soi
        self.case_study = case_study 
        self.gen = Prompter(logger=logger, system_prompt=SYSTEM_PROMPT)
        self.val = TestValidator(logger)

    def get_prompt(self, flight_trajectory, previous_obstacle_config):
        """
        Note:
            1. Move the obstacles along the based trajectory path and make sure UAV should crash.
            2. If best and worse fitness score is provide and they are very close, try something 
            different with obstacle configuration, may be rotation or substantial modification of 
            one of the obstacles.
            3. Try to make sure always consider the best fitness as reference and make modification 
            to make sure UAV will crash 
            4. Make DIVERSIFIED test cases, each test case should be different from the previous one.
        """
        prompt = f"""
        See below I will provide you Segment of Interest, the path UAV will follow to complete 
        his flight given that there are no obstacles.
        
        *** Segment of Interest (SOI) ***
        {self.soi}
        
        Once obstacles are provided, it will try to avoid the obstacle and still try to follow the same 
        path with sight modification to make sure it should not hit the obstacles.
        The goal here is to generate obstacle configurations to make sure that the UAV will crash by hitting 
        those obstacles. Below, I will provide you previous obstacle configurations in a specific format. You
        need to generate obstacle mutated configurations to make sure that UAV will crash and the path of 
        trajectory adopted by UAV to aviod hitting obstacle based on the provided obstacle configurations.
        
        *** Flight Trajectory Path ***
        {flight_trajectory}
        
        *** Previous Obstacle Configurations ***
        {previous_obstacle_config}
        
        Output:
            Just provide the yaml config no discription or explanation.
        """
        return prompt
    
    def get_duplicated_config_prompt(self):
        prompt = """
        The generated obstacle configuration is a duplicate of previous one. 
        Please generate a new obstacle configuration that is different from all previous configurations.
        Try agian to generate a new obstacle configuration.
        I will provide you previous obstacle configurations details as follow:
        """
        return prompt

    def generate_mutated_obstacles_config(self, flight_trajectory_path, previous_obstacle_config, test_dir, iter):
        
        # import previous flight trajectory for reference
        flight_trajectory = Helper.read_ulg(flight_trajectory_path, 30)
        # Load Yaml to get previous obstacle configuration
        obstacles = Helper.load_config(previous_obstacle_config)
        # Generate mutated obstacle configuration
        prompt = self.get_prompt(str(flight_trajectory), obstacles)
        first_trial, record = Helper.best_worse_fitness(f"results.csv")
        
        if first_trial:
            print("First Trial - No previous fitness record.")
            self.logger .info(f"Generated Prompt for LLM: \n {prompt}")
            resp = self.gen.process(prompt)
        else:
            prompt = prompt + "The best and worse cases are as follow, always try to pick the best config as reference while generating a new one as the goal is to make sure UAV will crash: \n " + record
            self.logger .info(f"Generated Prompt for LLM: \n {prompt}")
            resp = self.gen.process(prompt)
        
        parsed_data = Helper.parse_response(resp['reply'])
        
        # Sanity Checks
        overlapped = self.val.any_overlap(parsed_data['obstacles'])
        min_height_check = self.val.check_based_and_min_height(parsed_data['obstacles'])
        within_range = self.val.check_obstacle_parameter_ranges(parsed_data['obstacles'])
        test = Helper.get_hash(parsed_data)
        
        while True:
            if test in test_dir:
                print("Regenerating due to duplicate test case...")
                self.logger.info("Regenerating due to duplicate test case...")
                new_prompt = self.get_duplicated_config_prompt() + prompt
                self.logger.info(f"Regen Prompt: \n {new_prompt}")
                resp = self.gen.process(new_prompt)
                parsed_data = Helper.parse_response(resp['reply'])
                test = Helper.get_hash(parsed_data)
            else:
                self.logger.info("Got new unique test case, updating test directory")
                test_dir.add(test)
                self.logger.info(f"The Test Directory: {test_dir}")
                break
        
        ol_loop = 1
        while overlapped:
            print("Regenerating due to overlap...")
            self.logger.info(f"Regenerating due to overlap... iter:{ol_loop}")
            new_prompt = "We have overlapping obstacles in the previous configuration. Please generate a new configuration without any overlapping obstacles." + prompt
            self.logger.info(f"New Prompt to avoid overlappig: {new_prompt}")
            resp = self.gen.process(new_prompt)
            parsed_data = Helper.parse_response(resp['reply'])
            overlapped = self.val.any_overlap(parsed_data['obstacles'])
            ol_loop += 1
            print("Sanity Check - Any Overlap:", overlapped)
            
        mh_loop =1
        while not min_height_check:
            print("Regenerating due to min height violation...")
            self.logger.info(f"Regenerating due to overlap... iter:{mh_loop}")
            new_prompt = """
            Some obstacles do not meet the minimum height requirement or are not based on
            the ground. Please generate a new configuration that satisfies these conditions, obstacles must
            be placed directly on the ground (z = 0), be taller than UAV flight height (h > 10 m)
            """ + prompt
            self.logger.info(f"New Prompt to obtain minimum height: {new_prompt}")
            resp = self.gen.process(new_prompt)
            parsed_data = Helper.parse_response(resp['reply'])
            min_height_check = self.val.test_based_and_min_height(parsed_data['obstacles'])
            mh_loop += 1
            print("Sanity Check - Min Height Valid:", min_height_check)
        
        wr_loop =1 
        while not within_range:
            print("Regenerating due to parameter range violation...")
            self.logger.info(f"Regenerating due to overlap... iter:{wr_loop}")
            new_prompt = """
            Some obstacles have parameters that are out of the valid ranges. 
            Please generate a new configuration with all parameters within the specified ranges.
            """ + prompt
            self.logger.info(f"New Prompt to make sure we are within containts: {new_prompt}")
            resp = self.gen.process(new_prompt)
            parsed_data = Helper.parse_response(resp['reply'])
            within_range = self.val.check_obstacle_parameter_ranges(parsed_data['obstacles'])
            wr_loop += 1
            print("Sanity Check - Within Parameter Ranges:", within_range)
        
        with open(f"gen_config/mission_iter{iter}.yaml", "w", encoding="utf-8") as f:
            yaml.safe_dump(parsed_data, f, sort_keys=False, allow_unicode=True)
        
        return f"gen_config/mission_iter{iter}.yaml"
        
    