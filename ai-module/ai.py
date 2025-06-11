import os, sys, logging, argparse, math
from flask import Flask, json, jsonify, abort, make_response, request
from flask_restful import Api, Resource, reqparse
from modules.data_manager import DataManager
from modules.model_manager import ModelManager
from modules.evaluator import ModelEvaluator
from putils.autils import init_algorithms

THRESHOLD = 0.20

class AIModule:
    def __init__(self):
        self.models = {}
        self.training = {}
        self.testing = {}
        self.algorithms = {}
        self.dimensions = {}
        self.indexes = {}
        self.results = {}
        self.evaluator = ModelEvaluator(threshold=THRESHOLD)

    def add_model(self, name, algorithm, dimension, index):
        model = ModelManager(algorithm)

        ret = None
        if not model.get_error_status():
            self.models[name] = model
            self.algorithms[name] = algorithm
            self.dimensions[name] = dimension
            self.indexes[name] = index
            self.training[name] = DataManager()
            self.testing[name] = DataManager()
            self.results[name] = DataManager()
            self.results[name].add_data(-1)
            ret = self.models[name]
        else:
            print ("\n\nThere is an error!!!\n\n")

        return ret

    def has_model(self, name):
        return name in self.models

    def get_model(self, name):
        ret = None
        if name in self.models:
            ret = self.models[name]
        return ret

    def get_model_info(self, name):
        ret = {}
        if name in self.models:
            ret["name"] = name
        else:
            ret["name"] = "{} is not a generated model".format(name)

        if name in self.algorithms:
            ret["algorithm"] = self.algorithms[name]
        else:
            ret["algorithm"] = "no algorithm is specified"

        if name in self.dimensions:
            ret["dimension"] = self.dimensions[name]
            ret["index"] = self.indexes[name]
        else:
            ret["dimension"] = "no dimension is specified"
            ret["index"] = "no index is specified"

        return ret

    def get_data_info(self, name, dtype):
        ret = {}
        if name in self.models:
            ret["name"] = name
        else:
            ret["name"] = "{} is not a generated model".format(name)
            ret["opcode"] = "failure"

        if name in self.dimensions:
            ret["dimension"] = self.dimensions[name]
        else:
            ret["dimension"] = "no dimension is specified"
            ret["opcode"] = "failure"

        ret["dtype"] = dtype
        if dtype == "training":
            if name in self.training:
                ret["num"] = len(self.training[name])
            else:
                ret["num"] = "the training dataset for {} is not generated".format(name)
                ret["opcode"] = "failure"
        elif dtype == "testing":
            if name in self.testing:
                ret["num"] = len(self.testing[name])
            else:
                ret["num"] = "the testing dataset for {} is not generated".format(name)
                ret["opcode"] = "failure"
        else:
            ret["opcode"] = "failure"

        if "opcode" not in ret:
            ret["opcode"] = "success"

        return ret

    def get_model_names(self):
        return list(self.models.keys())

    def get_model_algorithm(self, name):
        ret = None
        if name in self.algorithms:
            ret = self.algorithms[name]
        return ret

    def get_model_dimension(self, name):
        ret = None
        if name in self.dimensions:
            ret = self.dimensions[name]
        return ret

    def get_model_power_index(self, name):
        ret = None
        if name in self.indexes:
            ret = self.indexes[name]
        return ret

    def add_training_data(self, name, value):
        logging.debug("before: {}".format(self.training[name].get_data()))
        self.training[name].add_data(value)
        logging.debug("after: {}".format(self.training[name].get_data()))

    def add_testing_data(self, name, value):
        self.testing[name].add_data(value)

    def get_result(self, name):
        sequence = self.testing[name].get_data()
        prediction = self.results[name].get_data()
        index = self.get_model_power_index(name)
        
        logging.debug("sequence> len: {}, sequence: {}".format(len(sequence), sequence))
        logging.debug("prediction> len: {}, prediction: {}".format(len(prediction), prediction))

        num = 0     # number of instances
        sidx = 0    # start index
        cp = 0      # correct prediction
        ip = 0      # incorrect prediction
        for i in range(len(sequence)):
            if prediction[i] == -1:
                sidx += 1
                continue
            num += 1
            if math.fabs((prediction[i] - sequence[i][index]) / sequence[i][index]) <= THRESHOLD:
                cp += 1
            else:
                ip += 1
        accuracy = round(cp / num * 100, 2)
        return num, sequence[sidx:], prediction[sidx:], index, THRESHOLD, cp, ip, accuracy
    
    def get_detailed_evaluation(self, name):
        """상세한 평가 지표를 계산하여 반환"""
        sequence = self.testing[name].get_data()
        prediction = self.results[name].get_data()
        index = self.get_model_power_index(name)
        
        if not sequence or not prediction:
            return {"error": "평가할 데이터가 없습니다"}
        
        # 새로운 평가 모듈 사용
        metrics = self.evaluator.calculate_metrics(sequence, prediction, index)
        return metrics
    
    def set_evaluation_threshold(self, threshold):
        """평가 임계값 변경"""
        global THRESHOLD
        THRESHOLD = threshold
        self.evaluator.set_threshold(threshold)
        logging.info(f"평가 임계값 변경: {threshold}")

    def learning(self, name):
        self.models[name]
        self.training[name]
        self.dimensions[name]
        return self.models[name].learning(self.training[name], self.dimensions[name])
        
    def prediction(self, name, value):
        pred = self.models[name].prediction(value, self.dimensions[name])
        index = self.indexes[name]
        logging.debug("pred in prediction(): {}".format(pred))
        self.results[name].add_data(pred[index])
        return pred

# URI: /
# HTTP behavior: GET
# GET: Get the available AI algorithms and available generated AI models
class Main(Resource):
    def get(self):
        model_list = {}
        model_list["algorithms"] = {}

        algorithms = [f.split(".py")[0] for f in os.listdir("algorithms") if ".py" in f and f != "algorithm.py"]
        model_list["algorithms"]["note"] = "available AI algorithms"
        model_list["algorithms"]["value"] = algorithms

        model_list["models"] = {}
        model_list["models"]["note"] = "available AI models"
        model_list["models"]["value"] = ai.get_model_names()

        return make_response(jsonify(model_list))

# URI: /<string: model_id>
# HTTP behavior: GET, POST
# GET: Get the information (algorithm, dimension) about the model
# POST: Make the model with the parameters (name, algorithm, dimension)
class ModelGenerator(Resource):
    def __init__(self):
        super(ModelGenerator, self).__init__()

    def get(self, model_id):
        info = ai.get_model_info(model_id)
        return make_response(jsonify(info))

    def post(self, model_id):
        ret = {}
        args =request.get_json(force=True)
        if "algorithm" not in args:
            ret["opcode"] = "failure"
            ret["reason"] = "the algorithm parameter is missing"
            return make_response(jsonify(ret))
        else:
            algorithm = args["algorithm"]

        if "dimension" not in args:
            dimension = 1
            if "index" not in args:
                index = 0
            else:
                index = args["index"]
        else:
            if "index" not in args:
                ret["opcode"] = "failure"
                ret["reason"] = "the index for the power value should be included if you do not use the default dimension (1)"
                return make_response(jsonify(ret))
            else:
                index = args["index"]
                dimension = args["dimension"]

        model = ai.add_model(model_id, algorithm, dimension, index)

        if not model:
            ret["opcode"] = "failure"
            ret["reason"] = "internal issue of the model manager"
        else:
            ret["opcode"] = "success"
        return make_response(jsonify(ret))

# URI: /<string: model_id>/training
# HTTP behavior: GET, POST, PUT
# GET: Get the information about the training data
# POST: Train the model with the training dataset
# PUT: Add the training data
class Trainer(Resource):
    def __init__(self):
        super(Trainer, self).__init__()

    def get(self, model_id):
        ret = ai.get_data_info(model_id, "training")
        return make_response(jsonify(ret))

    def post(self, model_id):
        ret = {}
        generated = ai.learning(model_id)
        if generated == True:
            ret["opcode"] = "success"
        else:
            ret["opcode"] = "failure"
            ret["reason"] = "creating the model {} failed".format(model_id)
        return make_response(jsonify(ret))

    def put(self, model_id):
        ret = {}
        if ai.has_model(model_id):
            args = request.get_json(force=True)
            if "value" not in args:
                ret["opcode"] = "failure"
                ret["reason"] = "the necessary attribute 'value' is not included"
            else:
                value = args["value"]
                logging.debug("value: {}".format(value))

                if len(value) != ai.get_model_dimension(model_id):
                    ret["opcode"] = "failure"
                    ret["reason"] = "not enough features. the dimension of the instance should be {} (the dimension of {} is given).".format(ai.get_model_dimension(model_id), len(value))
                else:
                    ret["opcode"] = "success"
                    ai.add_training_data(model_id, value)
        else:
            ret["opcode"] = "failure"
            ret["reason"] = "the model {} is unavailable".format(model_id)
        logging.debug("ret: {}".format(ret))
        return make_response(jsonify(ret))
        
# URI: /<string: model_id>/testing
# HTTP behavior: GET, PUT
# GET: Get the test results until now
# PUT: Add the test data and gets the expected next result
class Tester(Resource):
    def __init__(self):
        super(Tester, self).__init__()

    def get(self, model_id):
        ret = ai.get_data_info(model_id, "testing")
        return make_response(jsonify(ret))

    def put(self, model_id):
        ret = {}
        if ai.has_model(model_id):
            args = request.get_json(force=True)
            if "value" not in args:
                ret["opcode"] = "failure"
                ret["reason"] = "the necessary attribute 'value' is not included"
            else:
                value = args["value"]
                logging.debug("value: {}".format(value))

                if len(value) != ai.get_model_dimension(model_id):
                    ret["opcode"] = "failure"
                    ret["reason"] = "not enough features. the dimension of the instance should be {} (the dimension of {} is given).".format(ai.get_model_dimension(model_id, len(value)))
                else:
                    ai.add_testing_data(model_id, value)
                    result = ai.prediction(model_id, value)
                    logging.debug("result: {}".format(result))
                    ret["opcode"] = "success"
                    ret["prediction"] = result[ai.get_model_power_index(model_id)]
        else:
            ret["opcode"] = "failure"
            ret["reason"] = "the model {} is unavailable".format(model_id)
        return make_response(jsonify(ret))

# URI: /<string: model_id>/result
# HTTP behavior: GET
class Evaluator(Resource):
    def __init__(self):
        super(Evaluator, self).__init__()

    def get(self, model_id):
        ret = {}
        if ai.has_model(model_id):
            num, seq, pred, index, threshold, correct, incorrect, accuracy = ai.get_result(model_id)
            ret["opcode"] = "success"
            ret["num"] = num
            ret["sequence"] = seq
            ret["prediction"] = pred
            ret["index"] = index
            ret["threshold"] = str(threshold)
            ret["correct"] = correct
            ret["incorrect"] = incorrect
            ret["accuracy"] = str(accuracy)
        else:
            ret["opcode"] = "failure"
            ret["reason"] = "the model {} is unavailable".format(model_id)
        return make_response(jsonify(ret))

# URI: /<string: model_id>/detailed_evaluation
# HTTP behavior: GET
class DetailedEvaluator(Resource):
    def __init__(self):
        super(DetailedEvaluator, self).__init__()

    def get(self, model_id):
        ret = {}
        if ai.has_model(model_id):
            metrics = ai.get_detailed_evaluation(model_id)
            if "error" in metrics:
                ret["opcode"] = "failure"
                ret["reason"] = metrics["error"]
            else:
                ret["opcode"] = "success"
                ret["metrics"] = metrics
                ret["summary"] = ai.evaluator.get_performance_summary(metrics)
        else:
            ret["opcode"] = "failure"
            ret["reason"] = "the model {} is unavailable".format(model_id)
        return make_response(jsonify(ret))

# URI: /config/threshold
# HTTP behavior: GET, PUT
class ThresholdConfig(Resource):
    def __init__(self):
        super(ThresholdConfig, self).__init__()

    def get(self):
        ret = {
            "opcode": "success",
            "current_threshold": THRESHOLD,
            "description": "현재 설정된 정확도 판정 임계값 (상대 오차 기준)"
        }
        return make_response(jsonify(ret))

    def put(self):
        ret = {}
        args = request.get_json(force=True)
        if "threshold" not in args:
            ret["opcode"] = "failure"
            ret["reason"] = "threshold 값이 필요합니다"
        else:
            threshold = args["threshold"]
            if not isinstance(threshold, (int, float)) or threshold <= 0:
                ret["opcode"] = "failure"
                ret["reason"] = "threshold는 0보다 큰 숫자여야 합니다"
            else:
                ai.set_evaluation_threshold(threshold)
                ret["opcode"] = "success"
                ret["new_threshold"] = threshold
                ret["message"] = f"임계값이 {threshold}로 변경되었습니다"
        return make_response(jsonify(ret))

def command_line_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--addr", metavar="<IP address>", help="IP address", type=str, default="0.0.0.0")
    parser.add_argument("-p", "--port", required=True, metavar="<port number>", help="Port number", type=int)
    parser.add_argument("-l", "--log", metavar="<log level (DEBUG/INFO/WARNING/ERROR/CRITICAL)>", help="Log level (DEBUG/INFO/WARNING/ERROR/CRITICAL)", type=str, default="INFO")
    args = parser.parse_args()
    return args

def main():
    args = command_line_args()
    logging.basicConfig(level=args.log)

    global ai
    ai = AIModule()

    app = Flask(__name__)
    api = Api(app)
    api.add_resource(Main, '/')
    api.add_resource(ModelGenerator, '/<string:model_id>')
    api.add_resource(Trainer, '/<string:model_id>/training')
    api.add_resource(Tester, '/<string:model_id>/testing')
    api.add_resource(Evaluator, '/<string:model_id>/result')
    api.add_resource(DetailedEvaluator, '/<string:model_id>/detailed_evaluation')
    api.add_resource(ThresholdConfig, '/config/threshold')

    app.run(host=args.addr, port=args.port)

# The process when the application is starting
if __name__ == "__main__":
    main()
