import json
import os
import argparse
import pandas as pd
from pathlib import Path
from pathlib import Path

import yaml
from utils.helper import Helper
from testcase import TestCase
from test_validator import TestValidator
from aerialist.px4.aerialist_test import AerialistTest
from bot.prompter import Prompter
from bot.sys_prompts.gen_seed import get_system_prompt

from utils.logger import LoggerManager
logger = LoggerManager(name='Test Seed Generater',log_dir='logs', level='INFO').get_logger()

class SeedGenerator:
    def __init__(self, logger, soi, output_dir):
        self.output_dir = output_dir
        self.log = logger
        self.soi = soi
        xl,xh= Helper.get_x_limit(soi)
        self.gen = Prompter(logger, get_system_prompt(xl,xh))
        self.validator = TestValidator(logger)
        self.seeds_track = 0
        os.makedirs(output_dir, exist_ok=True)
        self.col = ["yaml_path", "ulg_path", "distance", "time", "obs1-size", "obs1-position", "obs2-size", "obs2-position"]
  
    def get_prompt(self):
        prompt = f"""
        See below I will provide you the Segment of Interest, path UAV will follow to complete 
        his flight given that there are no obstacles.
        
        *** Segment of Interest (SOI) ***
        {self.soi}
        
        Once obstacles are provided, it will try to avoid the obstacle and still try to follow the same 
        path with sight modification to make sure it should not hit the obstacles.
        The goal here is to generate obstacle configurations to make sure that the UAV will crash by hitting 
        those obstacles. 
        
        Goal:
            1. You are supposed to generate 10 very diversified config. Should differ from each other significantly and must be placed in the way of Segment of Interest.
            2. No Overlapping of obstacles in each test case.
            3. Don't place obstacles directly on the top of the other obstacle in a line.
            4. Obstacle should not placed directly at the starting point of SOI, we want to give room to UAV to atleast fly.
            
        Couple of good suggestion:
            1. Make sure one of the obstacle is on SOI or try to place obstacles in such a way that it will force the trajectory to follow the S shaped flight.
            2. ***Make sure one of the obstacle has width of 2m and has max length within the constraints and thats 20m and this one should placed close to the starting point of flight (y = 12)***
            3. To add diversity switch the positions too like moving left or right on SOI 
            4. Don't choose min length for obstacles while generating the test cases. 
            5. Place obstacle at horizontally and vertial distance between each obstacle is 20m.
            6. Each obstacle should be completely or partially placed on SOI path.
        """
        return prompt
    
    def strip_json_fence(self, text: str) -> str:
        """
        Remove ```json ... ``` fences from a model reply, compatible with older Python.
        """
        text = text.strip()

        if text.startswith("```json"):
            text = text[len("```json"):]
        elif text.startswith("```"):
            text = text[len("```"):]

        if text.endswith("```"):
            text = text[:-3]

        return text.strip()

    def generate_seeds(self):
        self.log.info("generating base seeds..")
        prompt = self.get_prompt()
        resp = self.gen.process(prompt)
        cleaned = self.strip_json_fence(resp["reply"])
        data = json.loads(cleaned)
        id =1
        for config in data:
            with open(f"{self.output_dir}/base_config_{id}.yaml", "w", encoding="utf-8") as f:
                yaml.safe_dump(config, f, sort_keys=False, allow_unicode=True)
            id +=1
            
    def verify_seed(self):
        yaml_files = list(Path(self.output_dir).rglob("*.yaml"))
        valid_records = []
        invalid_records = []
        for i, yaml_path in enumerate(yaml_files, start=1):
            with open(yaml_path, 'r', encoding='utf-8') as bs:
                base_data = yaml.safe_load(bs)

            obstacles = base_data["obstacles"]
            ok = self.validator.check_within_boundary(obstacles)
            val = Helper.get_config_info(str(yaml_path))
            record = {
                "file_path": str(yaml_path),
                "obs1_size": val.get("obs1_size"),
                "obs1_position": val.get("obs1_position"),
                "obs2_size": val.get("obs2_size"),
                "obs2_position": val.get("obs2_position"),
            }

            if ok:
                valid_records.append(record)
            else:
                invalid_records.append(record)

        df_valid = pd.DataFrame(valid_records)
        df_invalid = pd.DataFrame(invalid_records)

        self.log.info(f"Valid Configurations: {len(df_valid)}")
        self.log.info(f"Invalid Configurations:{ len(df_invalid)}")
        self.seeds_track = len(yaml_files)
        return df_valid, df_invalid

    def get_valid_seeds(self):
        self.generate_seeds()
        valid_seeds, invalid_seeds = self.verify_seed()
        while (len(valid_seeds) < 10):
            names = invalid_seeds["file_path"].tolist()
            self.log.info(f"invalid files = {len(names)}")
            invalid_seeds.drop(columns=["file_path"], inplace=True)
            prompt = f"""
            We got 10 configs and out of the 10 config, {len(valid_seeds)} configs are valid and 
            {len(invalid_seeds)} are in valid, below I will provide the details of the invalid configs
            as they were out of the defined rectangular test area (flight boundary), X ∈ [−40, 30], Y ∈ [10, 40]:
            {invalid_seeds.to_string(index=False)}
            
            Goal:
                1. Pick the invalid configs and mutate them, such that they will be inside the rectangular boundary.
                2. Generated Test should be diversified.
                3. Consider the valid configs too, to ensure the diversity beteewn the new and old configs. Old valid config are as follow:
                {valid_seeds.to_string(index=False)}
                4. if we got x invalid config, rectify all of them and return same number of configs
            """
            resp = self.gen.process(prompt)
            cleaned = self.strip_json_fence(resp["reply"])
            # Parse JSON into Python objects
            data = json.loads(cleaned)
            for config in data:
                with open(f"{self.output_dir}/base_config_{self.seeds_track + 1}.yaml", "w", encoding="utf-8") as f:
                    yaml.safe_dump(config, f, sort_keys=False, allow_unicode=True)
                self.seeds_track +=1
            valid_seeds, invalid_seeds = self.verify_seed()
        
        self.log.info("got 10 valid seeds.. lets go")
        valid_seeds, invalid_seeds = self.verify_seed()
        for _, row in invalid_seeds.iterrows(): 
            Helper.del_file(row['file_path'])
    
    def simulate_seed(self, base_yaml_file, test_cases):
        yaml_files = list(Path(self.output_dir).rglob("*.yaml"))
        self.log.info(f"Found {len(yaml_files)} YAML files.\n")
        for i, yaml_path in enumerate(yaml_files, start=1):
            self.log.info(f"Processing file: {yaml_path}")
            with open(yaml_path, 'r', encoding='utf-8') as bs:
                base_data = yaml.safe_load(bs)

            obstacles = base_data["obstacles"]
            test = TestCase(AerialistTest.from_yaml(base_yaml_file), Helper.to_px4_obstacles(obstacles))
            _, ulg_path = test.execute()
            self.log.info(f"Seed's ({yaml_path:}) flight logs stored at following path: {ulg_path}")
            distances = test.get_distances()
            print(f"minimum_distance:{min(distances)}")
            img_path = test.plot()
            self.log.info(f"Seed's ({yaml_path:}) image stored at following path: {img_path}")
            if min(distances) < 1.5:
                test_cases.append(test)
            Helper.write_csv(self.col, [yaml_path, ulg_path, min(distances), Helper.get_flight_time(ulg_path) ,obstacles[0]["size"], obstacles[0]['position'], obstacles[1]['size'], obstacles[1]['position']],f"{self.output_dir}/seeds_info.csv")
    
    def get_top_seeds(self, threshold=1.55):
        df = pd.read_csv(f"{self.output_dir}/seeds_info.csv")
        df_sorted = df.sort_values(by='distance', ascending=True)
        sel_conf = df_sorted[df_sorted["distance"] < threshold]
        return sel_conf['yaml_path'].tolist(), sel_conf, len(df_sorted)
    
    def get_seeds(self, base_yaml_file, test_cases):
        self.get_valid_seeds()
        self.simulate_seed(base_yaml_file, test_cases)
        return self.get_top_seeds()
        
        
def main():
    parser = argparse.ArgumentParser(
        description="Generate base UAV config from trajectory and YAML."
    )
    parser.add_argument(
        "--trajectory",
        "-t",
        type=Path,
        default=Path("soi/soi_1.ulg"),
        help="Path to the base trajectory file (.ulg).",
    )
    parser.add_argument(
        "--yaml",
        "-y",
        type=Path,
        default=Path("case_studies/mission2.yaml"),
        help="Path to the base YAML config file.",
    )

    args = parser.parse_args()

    # Optional: quick existence checks (remove if not desired)
    if not args.trajectory.exists():
        parser.error(f"Trajectory not found: {args.trajectory}")
    if not args.yaml.exists():
        parser.error(f"YAML not found: {args.yaml}")
    soi = Helper.read_ulg(str(args.trajectory),30)
    gen = SeedGenerator(logger, soi,"seeds")
    # gen.get_seeds(str(args.yaml))
    gen.generate_seeds()

if __name__ == "__main__":
    main()

