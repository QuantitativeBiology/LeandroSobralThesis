import json


class Params:

    def __init__(self, 
        num_epochs = 2000,
        batch_size = 128, 
        alpha = 0.2, 
        miss_rate = 0.2, 
        hint_rate = 0.9, 
        lr_D = 0.001, 
        lr_G = 0.001,
        num_runs = 1
        ):

        self.num_epochs = num_epochs
        self.batch_size = batch_size
        self.alpha = alpha
        self.miss_rate = miss_rate
        self.hint_rate = hint_rate
        self.lr_D = lr_D
        self.lr_G = lr_G
        self.num_runs = num_runs

    @staticmethod
    def read_json(json_file):
        with open(json_file, "r") as f:
            params = json.load(f)
        return params
    
    @classmethod
    def read_hyperparameters(cls, params_json=None):
        
        params = cls.read_json(params_json)

        print(params)
        
        num_epochs = params["num_epochs"]
        batch_size = params["batch_size"]
        alpha = params["alpha"]
        miss_rate = params["miss_rate"]
        hint_rate = params["hint_rate"]
        lr_D = params["lr_D"]
        lr_G = params["lr_G"]
        num_runs = params["num_runs"]

        return cls(num_epochs, batch_size, alpha, miss_rate, hint_rate, lr_D, lr_G, num_runs)
