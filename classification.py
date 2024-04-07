import os
if os.path.exists('/home/build'): 
    os.environ['HF_HOME'] = '/home/build'
else:
    os.environ['HF_HOME'] = './build'

os.environ['TOKENIZERS_PARALLELISM'] = 'False' #Disabling parallelism to avoid deadlocks...

from sentence_transformers import SentenceTransformer, util
from transformers import pipeline, AutoModelForSequenceClassification, AutoTokenizer

class Classification:
    def __init__(self):

        self.model_sts = None
        self.tokenizer_zs = None
        self.model_zs = None
        self.classifier_zs = None

    def load_Models(self):
        if os.path.exists('/home/build'): 
            #self.model_sts = SentenceTransformer('Sahajtomar/German-semantic',cache_folder="/home/build")
            self.model_sts = SentenceTransformer('deutsche-telekom/gbert-large-paraphrase-cosine',cache_folder="/home/build")

            if os.path.exists('/home/build/Sahajtomar_German_Zeroshot'): 
                self.tokenizer_zs = AutoTokenizer.from_pretrained("/home/build/Sahajtomar_German_Zeroshot")
            else:
                self.tokenizer_zs = AutoTokenizer.from_pretrained("Sahajtomar/German_Zeroshot")
                self.tokenizer_zs.save_pretrained("/home/build/Sahajtomar_German_Zeroshot")

            if os.path.exists('/home/build/Sahajtomar_German_Zeroshot'): 
                self.model_zs = AutoModelForSequenceClassification.from_pretrained("/home/build/Sahajtomar_German_Zeroshot")
            else:
                self.model_zs = AutoModelForSequenceClassification.from_pretrained("Sahajtomar/German_Zeroshot")
                self.model_zs.save_pretrained("/home/build/Sahajtomar_German_Zeroshot")        

        else:
            #self.model_sts = SentenceTransformer('Sahajtomar/German-semantic',cache_folder="./build")
            self.model_sts = SentenceTransformer('deutsche-telekom/gbert-large-paraphrase-cosine',cache_folder="./build")

            if os.path.exists('./build/Sahajtomar_German_Zeroshot'): 
                self.tokenizer_zs = AutoTokenizer.from_pretrained("./build/Sahajtomar_German_Zeroshot")
            else:
                self.tokenizer_zs = AutoTokenizer.from_pretrained("Sahajtomar/German_Zeroshot")
                self.tokenizer_zs.save_pretrained("./build/Sahajtomar_German_Zeroshot")

            if os.path.exists('./build/Sahajtomar_German_Zeroshot'): 
                self.model_zs = AutoModelForSequenceClassification.from_pretrained("./build/Sahajtomar_German_Zeroshot")
            else:
                self.model_zs = AutoModelForSequenceClassification.from_pretrained("Sahajtomar/German_Zeroshot")
                self.model_zs.save_pretrained("./build/Sahajtomar_German_Zeroshot")   


        #tokenizer_zs = AutoTokenizer.from_pretrained("Sahajtomar/German_Zeroshot")
        #tokenizer_zs.save_pretrained("/home/build/Sahajtomar_German_Zeroshot")
        #tokenizer_zs = AutoTokenizer.from_pretrained("/home/build/Sahajtomar_German_Zeroshot")


        #model_zs = AutoModelForSequenceClassification.from_pretrained("Sahajtomar/German_Zeroshot")
        #model_zs.save_pretrained("/home/build/Sahajtomar_German_Zeroshot")
        #model_zs = AutoModelForSequenceClassification.from_pretrained("/home/build/Sahajtomar_German_Zeroshot")

        self.classifier_zs = pipeline(task="zero-shot-classification",
                            model=self.model_zs,
                            tokenizer=self.tokenizer_zs)

        return

#---------------------------------------
    def predict_sts(self,sentences1:list[str],sentences2:list[str]):
        """sentences transformer"""
        if self.model_sts == None:
            return {
            "s1":sentences1,
            "s2":sentences2,
            "score": None }

        embeddings1 = self.model_sts.encode(sentences1, convert_to_tensor=True)
        embeddings2 = self.model_sts.encode(sentences2, convert_to_tensor=True)
        cosine_scores = util.pytorch_cos_sim(embeddings1, embeddings2)

        # for i in range(len(sentences1)):
        #     for j in range(len(sentences2)):
        #         print(cosine_scores[i][j])

        return {
            "s1":sentences1,
            "s2":sentences2,
            "score": cosine_scores.tolist() }

#---------------------------------------
    def predict_zs(self,sequence,candidate_labels):
        if self.classifier_zs == None:
            return {
                "sequence":sequence,
                "candidate_labels":candidate_labels,
                "score": None }        

        hypothesis_template = "Es handelt von {}."    ## Since monolingual model,its sensitive to hypothesis template. This can be experimented
        result = self.classifier_zs(sequence, candidate_labels, hypothesis_template=hypothesis_template)


        return {
            "sequence":sequence,
            "candidate_labels":candidate_labels,
            "score": result["scores"] }

#---------------------------------------
def main(args):
    print("start")
    log = ""
    #log = _train_save(args)
    myClassfication = Classification()
    myClassfication.load_Models()
    log = myClassfication.predict_sts(" ", "Berlin ist nicht klein")
    print(log)
    log = myClassfication.predict_zs(
        "Letzte Woche gab es einen Selbstmord in einer nahe gelegenen Kolonie.", 
        ["Verbrechen","Tragödie","Stehlen"]
        )
    print(log)

    #log = _predict_server(args)
    print("end")

    return {}

#---------------------------------------
#main({})
