import os, yaml, argparse
from time import sleep

from src.generator import Generator
from src.processor import Processor
from src.visualizer import Visualizer
os.environ['KMP_DUPLICATE_LIB_OK']='True'

def main():
    # Loading parameters
    parser = init_parser()
    args = parser.parse_args()

    args = update_parameters(parser, args)  # cmd > yaml > default

    # Waiting to run
    sleep(args.delay_hours * 3600)

    # Processing
    if args.generate_data:
        g = Generator(args)
        g.start()

    elif args.extract or args.visualize:
        if args.extract:
            p = Processor(args)
            p.extract()
        if args.visualize:
            v = Visualizer(args)
            v.start()

    else:
        p = Processor(args)
        p.start()


def init_parser():
    parser = argparse.ArgumentParser(description='Method for Skeleton-based Action Recognition')

    # Setting
    parser.add_argument('--config', '-c', type=str, default='2001', help='ID of the using config', required=True)
    parser.add_argument('--gpus', '-g', type=int, nargs='+', default=[], help='Using GPUs')
    parser.add_argument('--seed', '-s', type=int, default=1, help='Random seed')
    parser.add_argument('--pretrained_path', '-pp', type=str, default='', help='Path to pretrained models')
    parser.add_argument('--work_dir', '-w', type=str, default='', help='Work dir')
    parser.add_argument('--no_progress_bar', '-np', default=False, action='store_true', help='Do not show progress bar')
    parser.add_argument('--delay_hours', '-dh', type=float, default=0, help='Delay to run')

    # Processing
    parser.add_argument('--debug', '-db', default=False, action='store_true', help='Debug')
    parser.add_argument('--resume', '-r', default=False, action='store_true', help='Resume from checkpoint')
    parser.add_argument('--evaluate', '-e', default=False, action='store_true', help='Evaluate')
    parser.add_argument('--extract', '-ex', default=False, action='store_true', help='Extract')
    parser.add_argument('--visualize', '-v', default=False, action='store_true', help='Visualization')
    parser.add_argument('--generate_data', '-gd', default=False, action='store_true', help='Generate skeleton data')

    # Visualization
    parser.add_argument('--visualization_class', '-vc', type=int, default=0, help='Class: 1 ~ 60, 0 means true class')
    parser.add_argument('--visualization_sample', '-vs', type=int, default=0, help='Sample: 0 ~ batch_size-1')
    parser.add_argument('--visualization_frames', '-vf', type=int, nargs='+', default=[], help='Frame: 0 ~ max_frame-1')

    # Dataloader
    parser.add_argument('--dataset', '-d', type=str, default='', help='Select dataset')
    parser.add_argument('--dataset_args', default=dict(), help='Args for creating dataset')

    # Model
    parser.add_argument('--model_type', '-mt', type=str, default='', help='Args for creating model')
    parser.add_argument('--model_args', default=dict(), help='Args for creating model')
    
    # Optimizer
    parser.add_argument('--optimizer', '-o', type=str, default='', help='Initial optimizer')
    parser.add_argument('--optimizer_args', default=dict(), help='Args for optimizer')

    # LR_Scheduler
    parser.add_argument('--lr_scheduler', '-ls', type=str, default='', help='Initial learning rate scheduler')
    parser.add_argument('--scheduler_args', default=dict(), help='Args for scheduler')

    return parser


def update_parameters(parser, args):
    if os.path.exists('./configs/{}.yaml'.format(args.config)):
        with open('./configs/{}.yaml'.format(args.config), 'r') as f:
            try:
                yaml_arg = yaml.load(f, Loader=yaml.FullLoader)
            except:
                yaml_arg = yaml.load(f)
            default_arg = vars(args)
            for k in yaml_arg.keys():
                if k not in default_arg.keys():
                    raise ValueError('Do NOT exist this parameter {}'.format(k))
            parser.set_defaults(**yaml_arg)
    else:
        raise ValueError('Do NOT exist this file in \'configs\' folder: {}.yaml!'.format(args.config))
    return parser.parse_args()


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
