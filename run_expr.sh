model=meta-llama/Llama-2-70b-chat-hf
export SIMPLE_MODE=1
python3 run.py --group 3 --max_round 100 --model ${model} --max_id -399
python3 run.py --group 3 --max_round 100 --model ${model} --max_id -399
python3 run.py --group 3 --max_round 100 --model ${model} --max_id -399
unset SIMPLE_MODE
export SELF_VALIDATE=1 
export ENABLE_PP=1
python3 run.py --group 3 --max_round 100 --model ${model} --max_id -399
python3 run.py --group 3 --max_round 100 --model ${model} --max_id -399
python3 run.py --group 3 --max_round 100 --model ${model} --max_id -399