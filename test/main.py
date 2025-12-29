import gitlab
from datetime import datetime
import argparse
import sys

def get_label_history(project_id, issue_iid, gitlab_url=None, private_token=None):
    """
    Получает историю изменений меток для указанной задачи.
    
    Args:
        project_id: ID или путь к проекту (например, 'namespace/project')
        issue_iid: Внутренний ID задачи в проекте (IID)
        gitlab_url: URL GitLab инстанса (опционально, по умолчанию gitlab.com)
        private_token: Персональный токен доступа GitLab
    """
    
    # Подключение к GitLab
    try:
        if gitlab_url:
            gl = gitlab.Gitlab(url=gitlab_url, private_token=private_token)
        else:
            gl = gitlab.Gitlab(private_token=private_token)
        
        # Проверка аутентификации (не работает с job tokens)
        if private_token and 'CI_JOB_TOKEN' not in private_token:
            gl.auth()
        
        print(f"Успешно подключено к {gitlab_url or 'gitlab.com'}")
        
    except Exception as e:
        print(f"Ошибка подключения к GitLab: {e}")
        sys.exit(1)
    
    # Получение проекта
    try:
        project = gl.projects.get(project_id)
        print(f"Проект: {project.name} (ID: {project.id})")
    except Exception as e:
        print(f"Ошибка получения проекта {project_id}: {e}")
        sys.exit(1)
    
    # Получение задачи
    try:
        issue = project.issues.get(issue_iid)
        print(f"Задача: #{issue.iid} - {issue.title}")
        print(f"Текущие метки: {', '.join(issue.labels) if issue.labels else 'нет меток'}")
        print("-" * 50)
    except Exception as e:
        print(f"Ошибка получения задачи #{issue_iid}: {e}")
        sys.exit(1)
    
    # Получение событий меток
    # Для этой задачи используем Resource label events API [citation:2]
    try:
        # Получаем события меток через API
        label_events = issue.resourcelabelevents.list(get_all=True)
        
        if not label_events:
            print("История изменений меток не найдена.")
            return
        
        print(f"Найдено {len(label_events)} событий с метками:\n")
        
        # Обработка и вывод событий
        events_by_date = []
        
        for event in label_events:
            # Преобразуем время события
            created_at = datetime.fromisoformat(event.created_at.replace('Z', '+00:00'))
            
            # Определяем тип действия
            action = event.action
            if action == "add":
                action_text = "добавлена"
            elif action == "remove":
                action_text = "удалена"
            else:
                action_text = action
            
            # Получаем информацию о пользователе
            user_name = "Неизвестный пользователь"
            if hasattr(event, 'user') and event.user:
                user_name = event.user.get('name', 'Неизвестный пользователь')
            elif hasattr(event, 'author') and event.author:
                user_name = event.author.get('name', 'Неизвестный пользователь')
            
            event_info = {
                'timestamp': created_at,
                'label': event.label.get('name', 'Неизвестная метка') if event.label else 'Неизвестная метка',
                'action': action_text,
                'user': user_name,
                'raw_action': action
            }
            events_by_date.append(event_info)
        
        # Сортируем события по времени
        events_by_date.sort(key=lambda x: x['timestamp'])
        
        # Выводим события в хронологическом порядке
        for i, event in enumerate(events_by_date, 1):
            print(f"{i}. {event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Метка: '{event['label']}' {event['action']}")
            print(f"   Пользователь: {event['user']}")
            
            # Дополнительная информация, если доступна
            if hasattr(event, 'label') and event.label and 'id' in event.label:
                print(f"   ID метки: {event.label['id']}")
            
            print()
        
        # Сводная статистика
        print("=" * 50)
        print("Сводная статистика:")
        
        added_labels = [e for e in events_by_date if e['raw_action'] == 'add']
        removed_labels = [e for e in events_by_date if e['raw_action'] == 'remove']
        
        print(f"Всего добавлений меток: {len(added_labels)}")
        print(f"Всего удалений меток: {len(removed_labels)}")
        
        # Уникальные метки
        unique_labels = set(e['label'] for e in events_by_date)
        print(f"Уникальные метки в истории: {', '.join(sorted(unique_labels))}")
        
        # Временной диапазон
        if events_by_date:
            first_event = events_by_date[0]['timestamp']
            last_event = events_by_date[-1]['timestamp']
            print(f"Период истории: с {first_event.strftime('%Y-%m-%d')} по {last_event.strftime('%Y-%m-%d')}")
            
    except Exception as e:
        print(f"Ошибка при получении истории меток: {e}")
        
        # Альтернативный метод: получение через общие события задачи
        try:
            print("\nПопытка получения через общие события задачи...")
            events = issue.notes.list(get_all=True)
            
            label_events_filtered = []
            for note in events:
                if note.system and 'label' in note.body.lower():
                    created_at = datetime.fromisoformat(note.created_at.replace('Z', '+00:00'))
                    label_events_filtered.append({
                        'timestamp': created_at,
                        'description': note.body,
                        'author': note.author.get('name', 'Неизвестный пользователь')
                    })
            
            if label_events_filtered:
                print(f"\nНайдено {len(label_events_filtered)} системных событий с метками:\n")
                for i, event in enumerate(sorted(label_events_filtered, key=lambda x: x['timestamp']), 1):
                    print(f"{i}. {event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"   Действие: {event['description']}")
                    print(f"   Автор: {event['author']}\n")
            else:
                print("События с метками не найдены в системных заметках.")
                
        except Exception as e2:
            print(f"Ошибка при получении системных событий: {e2}")

def main():
    parser = argparse.ArgumentParser(
        description='Получение истории изменений меток для задачи GitLab',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python gitlab_label_history.py --project 123 --issue 45
  python gitlab_label_history.py --project mygroup/myproject --issue 7 --url https://gitlab.example.com
        """
    )
    
    parser.add_argument('--project', required=True, help='ID или путь к проекту (например: namespace/project)')
    parser.add_argument('--issue', required=True, type=int, help='IID задачи (номер задачи в проекте)')
    parser.add_argument('--url', help='URL GitLab инстанса (по умолчанию: gitlab.com)')
    parser.add_argument('--token', required=True, help='Персональный токен доступа GitLab')
    
    args = parser.parse_args()
    
    # Получение истории меток
    get_label_history(
        project_id=args.project,
        issue_iid=args.issue,
        gitlab_url=args.url,
        private_token=args.token
    )

if __name__ == "__main__":
    main()