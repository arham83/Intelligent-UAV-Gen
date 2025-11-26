import time
from pathlib import Path
from bot.core.bot_init_thread import Bot

class Prompter:
    """
    Generates the submisson method on fly
    """
    def __init__(self, logger, system_prompt):
        self.logger = logger
        self.bot = Bot(logger=logger, system_prompt=system_prompt)

    def process(self, prompt, img_path=None, file_path=None, max_retries=3, backoff_factor=2):
        file_id = self.bot.upload_file(Path(file_path)) if file_path is not None else None
        image_id = self.bot.upload_image(Path(img_path)) if img_path is not None else None
        thread = self.bot.create_thread()

        retries = 0
        while retries < max_retries:
            try:
                raw_resp = self.bot.post_message_to_thread(
                    thread_id=thread.id,
                    prompt_text=prompt,
                    file_id=file_id,
                    image_id=image_id,
                )
                # Success: write JSON and break
                self.logger.info(f"Generated submission method code:\n{raw_resp}")
                return raw_resp
            except Exception as e:
                self.logger.error(f"Error during OpenAI request: {e}")
                retries += 1
                if retries < max_retries:
                    wait_time = backoff_factor ** retries
                    self.logger.warning(f"Retrying in {wait_time} seconds... (Attempt {retries}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    self.logger.error("Max retries reached. Failing gracefully.")
