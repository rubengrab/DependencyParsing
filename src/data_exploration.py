import pylab
import json
import embedding as em

if __name__ == '__main__':
    metrics = {
        'en': {
            'train': {
                'size': 0,
                'total_sentence_len': 0,
                'total_dep_len': 0,
                'average_sent_len': 0,
                'average_dep_len': 0
            },
            'validate': {
                'size': 0,
                'total_sentence_len': 0,
                'total_dep_len': 0,
                'average_sent_len': 0,
                'average_dep_len': 0
            },
            'test': {
                'size': 0,
                'total_sentence_len': 0,
                'total_dep_len': 0,
                'average_sent_len': 0,
                'average_dep_len': 0
            }
        },
        'ro': {
            'train': {
                'size': 0,
                'total_sentence_len': 0,
                'total_dep_len': 0,
                'average_sent_len': 0,
                'average_dep_len': 0
            },
            'validate': {
                'size': 0,
                'total_sentence_len': 0,
                'total_dep_len': 0,
                'average_sent_len': 0,
                'average_dep_len': 0
            },
            'test': {
                'size': 0,
                'total_sentence_len': 0,
                'total_dep_len': 0,
                'average_sent_len': 0,
                'average_dep_len': 0
            }
        }
    }
    for language in metrics.keys():
        datasets = {}
        if language == 'en':
            datasets['train'] = em.en_train_sentences()
            datasets['validate'] = em.en_dev_sentences()
            datasets['test'] = em.en_test_sentences()
        elif language == 'ro':
            datasets['train'] = em.ro_train_sentences()
            datasets['validate'] = em.ro_dev_sentences()
            datasets['test'] = em.ro_test_sentences()

        for dataset, sentences in datasets.items():
            metrics[language][dataset]['size'] = len(sentences)
            for sentence in sentences:
                metrics[language][dataset]['total_sentence_len'] += len(sentence.words[1:])
                for index, head in enumerate(sentence.get_head_representation()):
                    metrics[language][dataset]['total_dep_len'] += int(abs(head - index))
            metrics[language][dataset]['average_sent_len'] = metrics[language][dataset]['total_sentence_len'] / metrics[language][dataset]['size']
            metrics[language][dataset]['average_dep_len'] = metrics[language][dataset]['total_dep_len'] / metrics[language][dataset]['total_sentence_len']

    print(json.dumps(metrics, indent=2))