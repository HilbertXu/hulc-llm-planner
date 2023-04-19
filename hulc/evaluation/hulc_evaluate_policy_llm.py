import argparse
import logging
from pathlib import Path
import sys

# This is for using the locally installed repo clone when using slurm
# from calvin_agent.evaluation.evaluate_policy_llm import evaluate_policy

sys.path.insert(0, Path(__file__).absolute().parents[2].as_posix())
from calvin_agent.evaluation.utils import get_default_model_and_env
from calvin_agent.utils.utils import get_all_checkpoints, get_checkpoints_for_epochs, get_last_checkpoint
from pytorch_lightning import seed_everything

from calvin_agent.evaluation.calvin_robot_manager import CALVINRobotManager

from calvin_agent.evaluation.utils import (
    collect_plan,
    count_success,
    create_tsne,
    get_default_model_and_env,
    get_env_state_for_initial_condition,
    get_log_dir,
    join_vis_lang,
    print_and_save,
)

logger = logging.getLogger(__name__)


def get_epoch(checkpoint):
    if "=" not in checkpoint.stem:
        return "0"
    checkpoint.stem.split("=")[1]

def get_cohere_api_key(file_path):
    if file_path is not None:
        # Read the API key from a text file
        with open(file_path, "r") as f:
            api_key = f.read().strip()
    else:
        api_key = None
    return api_key

def main():
    seed_everything(0, workers=True)  # type:ignore
    parser = argparse.ArgumentParser(description="Evaluate a trained model on multistep sequences with language goals.")
    parser.add_argument("--dataset_path", type=str, help="Path to the dataset root directory.")

    # arguments for loading default model
    parser.add_argument(
        "--train_folder", type=str, help="If calvin_agent was used to train, specify path to the log dir."
    )
    parser.add_argument(
        "--checkpoints",
        type=str,
        default=None,
        help="Comma separated list of epochs for which checkpoints will be loaded",
    )
    parser.add_argument(
        "--checkpoint",
        type=str,
        default=None,
        help="Path of the checkpoint",
    )
    parser.add_argument(
        "--last_k_checkpoints",
        type=int,
        help="Specify the number of checkpoints you want to evaluate (starting from last). Only used for calvin_agent.",
    )

    parser.add_argument("--debug", action="store_true", help="Print debug info and visualize environment.")

    parser.add_argument("--eval_log_dir", default=None, type=str, help="Where to log the evaluation results.")

    parser.add_argument("--device", default=0, type=int, help="CUDA device")
    
    parser.add_argument("--planner", default='openai', type=str, help="One of [truth, user, cohere, openai].")

    parser.add_argument("--cohere-path", default=None, type=str, help="Path of Cohere API key.")

    args = parser.parse_args()

    assert "train_folder" in args

    checkpoints = []
    if args.checkpoints is None and args.last_k_checkpoints is None and args.checkpoint is None:
        print("Evaluating model with last checkpoint.")
        checkpoints = [get_last_checkpoint(Path(args.train_folder))]
    elif args.checkpoints is not None:
        print(f"Evaluating model with checkpoints {args.checkpoints}.")
        checkpoints = get_checkpoints_for_epochs(Path(args.train_folder), args.checkpoints)
    elif args.checkpoints is None and args.last_k_checkpoints is not None:
        print(f"Evaluating model with last {args.last_k_checkpoints} checkpoints.")
        checkpoints = get_all_checkpoints(Path(args.train_folder))[-args.last_k_checkpoints :]
    elif args.checkpoint is not None:
        checkpoints = [Path(args.checkpoint)]

    env = None
    for checkpoint in checkpoints:
        epoch = get_epoch(checkpoint)
        model, env, _ = get_default_model_and_env(
            args.train_folder,
            args.dataset_path,
            checkpoint,
            env=env,
            device_id=args.device,
        )
        cohere_api_key = get_cohere_api_key(args.cohere_path)
        # evaluate_policy(model, env, epoch, eval_log_dir=args.eval_log_dir, debug=args.debug, create_plan_tsne=True)
        
        robo_manager = CALVINRobotManager(model, env, eval_log_dir=args.eval_log_dir, visualize=True, cohere_api_key=cohere_api_key)
        env_str, task_str, actions_str = robo_manager.reset_env()

        # task_str = "place the blue block into the lower drawer and turn off the bulb"
        task_str = "turn off the led, pick the pink block and place it in the drawer, then turn off the lightbulb"
        
        chosen_actions = robo_manager.select_subtask_sequence(env_str, task_str, actions_str, args.planner)
        
        print("\nThe following plan was chosen:")
        print(chosen_actions)
        input("\nPress [Enter] to continue...")
        print(env.get_info()["scene_info"]["fixed_objects"])
        for action in chosen_actions:
            success = robo_manager.rollout(action)
            print(f"{action} succesful? {success}")
            robo_manager.get_current_env_description()
            print("="*20)
        
        


if __name__ == "__main__":
    main()
