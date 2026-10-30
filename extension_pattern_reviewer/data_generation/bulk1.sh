#!/bin/bash
cd /Users/geboou/Desktop/oversight/finetune/v2
python3 gen.py --model nano-gpt/deepseek/deepseek-v4.1-flash --family deepseek --cls fraud --n 70 --seed 1001 --out out --workers 3
python3 gen.py --model nano-gpt/deepseek/deepseek-v4.1-flash --family deepseek --cls clean --n 100 --seed 1002 --out out --workers 3
python3 gen.py --model nano-gpt/deepseek/deepseek-v4-pro --family deepseek --cls fraud --n 70 --seed 1003 --out out --workers 3
python3 gen.py --model nano-gpt/deepseek/deepseek-v4-pro --family deepseek --cls clean --n 100 --seed 1004 --out out --workers 3
echo BULK1_DONE
