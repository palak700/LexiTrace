from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from backend.app.core.labels import LABELS


def compute_classification_metrics(labels,predictions):
    if not len(labels) or len(labels)!=len(predictions):
        raise ValueError('Evaluation needs equally sized, nonempty labels and predictions.')
    if not set(labels)<= set(range(len(LABELS))) or not set(predictions)<= set(range(len(LABELS))):
        raise ValueError('Evaluation supports only product labels 0/1/2.')
    precision,recall,f1,_=precision_recall_fscore_support(labels,predictions,labels=list(range(len(LABELS))),average='macro',zero_division=0)
    return {'accuracy':float(accuracy_score(labels,predictions)),'precision_macro':float(precision),
            'recall_macro':float(recall),'f1_macro':float(f1)}


def confusion_matrix_as_list(labels,predictions):
    return confusion_matrix(labels,predictions,labels=list(range(len(LABELS)))).tolist()
