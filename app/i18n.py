"""Translations for the public story experience. Language is explicit in shared URLs."""
LANGUAGES = {"en": "English", "ru": "Русский", "zh": "中文"}


def language(value):
    return value if value in LANGUAGES else "en"


COPY = {
    'archive': {"en": 'Explore the archive', "ru": 'Открыть архив', "zh": '探索档案'},
    'home_title': {"en": 'Every place has a story.', "ru": 'У каждого места есть история.', "zh": '每个地方都有故事。'},
    'home_intro': {"en": 'Turn a place into a short, illustrated journey. Start with a name or a link.', "ru": 'Превратите место в короткую историю с фотографиями. Начните с названия или ссылки.', "zh": '用照片和文字开启一段简短旅程。输入地点名称或链接即可。'},
    'input_label': {"en": 'Place name or article link', "ru": 'Название места или ссылка на статью', "zh": '地点名称或文章链接'},
    'placeholder': {"en": 'Bolshoi Theatre, Moscow — or https://…', "ru": 'Большой театр, Москва — или https://…', "zh": '莫斯科大剧院 — 或 https://…'},
    'create': {"en": 'Discover its story', "ru": 'Открыть историю', "zh": '探索故事'},
    'hint': {"en": 'Names work in Russian, English and Chinese. Add a city to narrow the search.', "ru": 'Можно вводить на русском, английском и китайском. Добавьте город, чтобы уточнить поиск.', "zh": '支持俄语、英语和中文名称。添加城市可缩小搜索范围。'},
    'latest': {"en": 'Stories to discover', "ru": 'Истории, которые стоит открыть', "zh": '发现更多故事'},
    'short': {"en": 'A story in about 3 minutes', "ru": 'История примерно за 3 минуты', "zh": '约三分钟，读懂一个地方'},
    'sources': {"en": 'Sources', "ru": 'Источники', "zh": '来源'},
    'photos': {"en": 'Archive photographs', "ru": 'Архивные фотографии', "zh": '档案照片'},
    'voices': {"en": 'Help preserve a memory', "ru": 'Помогите сохранить воспоминания', "zh": '帮助留住记忆'},
    'voices_text': {"en": 'Do you have a photograph or a memory of this place? Add your chapter to its story.', "ru": 'У вас есть фотография или воспоминание об этом месте? Добавьте свою главу в его историю.', "zh": '您有这个地方的照片或回忆吗？为它的故事添上一章。'},
    'share_memory': {"en": 'Share a memory', "ru": 'Поделиться воспоминанием', "zh": '分享回忆'},
    'choose': {"en": 'Which place did you mean?', "ru": 'Какое место вы имели в виду?', "zh": '您指的是哪个地方？'},
    'choose_hint': {"en": 'Check the description before creating a story.', "ru": 'Проверьте описание перед созданием истории.', "zh": '创建故事前，请核对地点描述。'},
    'no_results': {"en": 'No places with a Wikipedia article found. Try another name or paste an article link.', "ru": 'Не нашли места со статьёй в Википедии. Уточните название или вставьте ссылку на статью.', "zh": '未找到有维基百科条目的地点。请尝试其他名称或粘贴文章链接。'},
    'search_error': {"en": 'Search is temporarily unavailable. Try again or paste an article link.', "ru": 'Поиск временно недоступен. Попробуйте снова или вставьте ссылку на статью.', "zh": '搜索暂时不可用。请重试或粘贴文章链接。'},
    'invalid_input': {"en": 'Enter a place name (2–200 characters) or an HTTP(S) link.', "ru": 'Введите название места (2–200 символов) или HTTP(S)-ссылку.', "zh": '请输入地点名称（2–200个字符）或 HTTP(S) 链接。'},
    'back': {"en": 'Back', "ru": 'Назад', "zh": '返回'},
    'next': {"en": 'Next chapter', "ru": 'Следующая глава', "zh": '下一章'},
    'previous': {"en": 'Previous chapter', "ru": 'Предыдущая глава', "zh": '上一章'},
    'restart': {"en": 'Read again', "ru": 'Прочитать снова', "zh": '再读一遍'},
    'chapter': {"en": 'Chapter', "ru": 'Глава', "zh": '章节'},
    'dossier': {"en": 'Full archive record', "ru": 'Подробные материалы архива', "zh": '完整档案'},
    'listen': {"en": 'Listen', "ru": 'Слушать', "zh": '收听'},
    'stop': {"en": 'Stop audio', "ru": 'Остановить', "zh": '停止播放'},
    'share': {"en": 'Copy story link', "ru": 'Скопировать ссылку', "zh": '复制故事链接'},
    'copied': {"en": 'Link copied', "ru": 'Ссылка скопирована', "zh": '链接已复制'},
    'copy_error': {"en": 'Copy the address from your browser to share this story.', "ru": 'Чтобы поделиться, скопируйте адрес из браузера.', "zh": '请复制浏览器地址以分享故事。'},
    'fallback': {"en": 'This story is shown in its original language. A translation is not available yet.', "ru": 'История показана на языке оригинала. Перевод пока не готов.', "zh": '此故事以原文显示，译文尚未就绪。'},
    'translate': {"en": 'Prepare story in three languages', "ru": 'Подготовить историю на трёх языках', "zh": '生成三种语言的故事'},
    'disabled': {"en": 'New stories are currently added by curators.', "ru": 'Новые истории пока добавляют кураторы.', "zh": '新故事目前由策展人添加。'},
    'working': {"en": 'Preparing your story…', "ru": 'Готовим вашу историю…', "zh": '正在准备您的故事…'},
    'done': {"en": 'Done', "ru": 'Готово', "zh": '已完成'},
    'failed': {"en": 'Something went wrong', "ru": 'Что-то пошло не так', "zh": '出现了问题'},
    'open': {"en": 'Open the story', "ru": 'Открыть историю', "zh": '打开故事'},
    'wait': {"en": 'Collecting sources and preparing the story. You can leave this page open.', "ru": 'Собираем источники и готовим историю. Эту страницу можно оставить открытой.', "zh": '正在收集资料并准备故事。您可以保持此页面打开。'},
    'empty': {"en": 'No stories found.', "ru": 'Истории не найдены.', "zh": '未找到故事。'},
    'search': {"en": 'Search', "ru": 'Найти', "zh": '搜索'},
    'all': {"en": 'All places', "ru": 'Все места', "zh": '全部地点'},
    'unknown': {"en": 'Not assessed', "ru": 'Не оценено', "zh": '未评估'},
    'stable': {"en": 'Stable', "ru": 'Стабильное состояние', "zh": '状况稳定'},
    'watch': {"en": 'Watch', "ru": 'Требует внимания', "zh": '需关注'},
    'at_risk': {"en": 'At risk', "ru": 'Под угрозой', "zh": '面临风险'},
    'critical': {"en": 'Critical', "ru": 'Критическое состояние', "zh": '状况危急'},
    'lost': {"en": 'Lost or closed', "ru": 'Утрачено или закрыто', "zh": '已消失或关闭'},
    'no_source': {"en": 'Source not linked', "ru": 'Источник не указан', "zh": '未关联来源'},
    'no_photos': {"en": 'The story continues in the archive', "ru": 'История продолжается в архиве', "zh": '故事在档案中延续'},
    'skip': {"en": 'Skip to content', "ru": 'Перейти к содержимому', "zh": '跳至内容'},
    'curators': {"en": 'Curators', "ru": 'Кураторам', "zh": '策展人'},
    'language': {"en": 'Language', "ru": 'Язык', "zh": '语言'},
    'basic': {"en": 'A basic record is available; illustrated stories and translations require the story generation service.', "ru": 'Доступна базовая запись; для создания историй и переводов нужен сервис генерации.', "zh": '可创建基础档案；故事与翻译需要启用生成服务。'},
}

def translate(key, lang):
    return COPY.get(key, {}).get(language(lang), key)

COPY.update({
'read_story': {"en": 'Read the story', "ru": 'Читать историю', "zh": '阅读故事'},
'contribute': {"en": 'Contribute', "ru": 'Дополнить историю', "zh": '补充故事'},
'contribute_title': {"en": 'Do you have a piece of this story?', "ru": 'У вас есть частичка этой истории?', "zh": '您是否珍藏着这个地方的故事？'},
'contribute_intro': {"en": 'Share a photograph, a video or a memory of this place. Your contribution can help keep its story alive.', "ru": 'Поделитесь фотографией, видео или воспоминанием об этом месте. Ваш материал поможет сохранить его историю.', "zh": '分享这里的照片、视频或回忆，让这个地方的故事继续流传。'},
'send_photo': {"en": 'Upload a photograph', "ru": 'Загрузить фотографию', "zh": '上传照片'},
'send_video': {"en": 'Share a video', "ru": 'Поделиться видео', "zh": '分享视频'},
'video_link': {"en": 'video link', "ru": 'ссылка на видео', "zh": '视频链接'},
'text_voice': {"en": 'Text or voice recording', "ru": 'Текст или голосовая запись', "zh": '文字或录音'},
'review_note': {"en": 'Every submission is reviewed by a curator. Nothing is published automatically.', "ru": 'Каждый материал проверяет куратор. Ничего не публикуется без одобрения.', "zh": '所有投稿均由策展人审核，不会自动公开。'},
'video_intro': {"en": 'Upload an MP4 or WebM video (up to 50 MB), or paste a public video link.', "ru": 'Загрузите видео MP4 или WebM (до 50 МБ) или вставьте ссылку на общедоступное видео.', "zh": '上传 MP4 或 WebM 视频（最大50 MB），或粘贴公开视频链接。'},
'file': {"en": 'Video file', "ru": 'Видеофайл', "zh": '视频文件'},
'or_link': {"en": 'Or a link', "ru": 'Или ссылка', "zh": '或链接'},
'title': {"en": 'Title', "ru": 'Название', "zh": '标题'},
'description': {"en": 'What does it show?', "ru": 'Что на записи?', "zh": '视频内容是什么？'},
'author': {"en": 'Your name (optional)', "ru": 'Ваше имя (необязательно)', "zh": '您的姓名（选填）'},
'send_review': {"en": 'Send for review', "ru": 'Отправить на одобрение', "zh": '提交审核'},
'video_consent': {"en": 'I have the right to share this material and allow it to be displayed on this archive after approval.', "ru": 'У меня есть право поделиться этим материалом. Я разрешаю показывать его в архиве после одобрения.', "zh": '我有权分享此内容，并同意审核通过后在本档案展示。'},
})

COPY.update({
'globe_filter': {"en":'Filter places',"ru":'Фильтр мест',"zh":'筛选地点'},
'globe_hint': {"en":'Drag to rotate · Pinch or + / − to zoom · Select a place',"ru":'Вращайте пальцем · Приближайте щипком или + / − · Выберите место',"zh":'拖动旋转 · 双指或 + / − 缩放 · 选择地点'},
'zoom_in': {"en":'Zoom in',"ru":'Приблизить',"zh":'放大'},
'zoom_out': {"en":'Zoom out',"ru":'Отдалить',"zh":'缩小'},
'reset_globe': {"en":'Reset globe',"ru":'Сбросить вид',"zh":'重置视图'},
'globe_error': {"en":'Globe unavailable. Browse the places in the archive.',"ru":'Глобус недоступен. Места можно открыть в архиве.',"zh":'地球视图不可用，请浏览档案。'},
'globe_title': {"en":'Explore the world’s heritage',"ru":'Культурное наследие мира',"zh":'探索世界遗产'},
})

COPY.update({
'label_0': {"en":'Archive',"ru":'Архив',"zh":'档案'},
'label_1': {"en":'Passport',"ru":'Паспорт',"zh":'保护档案'},
'label_2': {"en":'Through time',"ru":'Сквозь время',"zh":'历史沿革'},
'label_3': {"en":'Living heritage',"ru":'Живое наследие',"zh":'活态遗产'},
'label_4': {"en":'Memories',"ru":'Воспоминания',"zh":'回忆'},
'label_5': {"en":'At risk',"ru":'Под угрозой',"zh":'面临风险'},
'label_6': {"en":'Facts & sources',"ru":'Факты и источники',"zh":'事实与来源'},
'label_7': {"en":'Layer 01 · Time',"ru":'Слой 01 · Время',"zh":'第一层 · 时间'},
'label_8': {"en":'Layer 02 · People',"ru":'Слой 02 · Люди',"zh":'第二层 · 人物'},
'label_9': {"en":'Layer 03 · Risk',"ru":'Слой 03 · Риски',"zh":'第三层 · 风险'},
'label_10': {"en":'Intangible heritage',"ru":'Нематериальное наследие',"zh":'非物质文化遗产'},
'label_11': {"en":'People who keep it alive',"ru":'Люди, сохраняющие традицию',"zh":'传承者'},
'label_12': {"en":'Glossary',"ru":'Словарь',"zh":'术语'},
'label_13': {"en":'Recordings',"ru":'Записи',"zh":'影像与录音'},
'label_14': {"en":'Heritage at risk',"ru":'Наследие под угрозой',"zh":'面临风险的遗产'},
'label_15': {"en":'In the news',"ru":'В новостях',"zh":'相关新闻'},
'label_16': {"en":'Archival Dossier',"ru":'Архивное досье',"zh":'档案资料'},
'label_17': {"en":'Preservation Passport',"ru":'Паспорт сохранения',"zh":'保护档案'},
'label_18': {"en":'Location',"ru":'Расположение',"zh":'位置'},
'label_19': {"en":'Coordinates',"ru":'Координаты',"zh":'坐标'},
'label_20': {"en":'Risk Status',"ru":'Состояние',"zh":'保护现状'},
'label_21': {"en":'Protection Status',"ru":'Охранный статус',"zh":'保护级别'},
'label_22': {"en":'Archive evidence',"ru":'Материалы архива',"zh":'档案依据'},
'label_23': {"en":'How to help & preserve',"ru":'Как помочь сохранению',"zh":'如何参与保护'},
'label_24': {"en":'Quick facts',"ru":'Кратко',"zh":'概况'},
'label_25': {"en":'At a glance',"ru":'Главные факты',"zh":'一览'},
'label_26': {"en":'Did you know?',"ru":'Знаете ли вы?',"zh":'您知道吗？'},
'label_27': {"en":'Where this comes from',"ru":'Откуда эта информация',"zh":'资料来源'},
'label_28': {"en":'Undated photographs',"ru":'Фотографии без даты',"zh":'未注明日期的照片'},
'label_29': {"en":'Sources',"ru":'Источники',"zh":'来源'},
'label_30': {"en":'All',"ru":'Все',"zh":'全部'},
'label_31': {"en":'No recordings yet. Performances, interviews and craft demonstrations are welcome.',"ru":'Записей пока нет. Вы можете прислать выступления, интервью или демонстрации ремёсел.',"zh":'暂无影像资料，欢迎提交演出、访谈或工艺展示。'},
'label_32': {"en":'No memories yet. Were you here? Your story is exactly what this archive is missing.',"ru":'Пока нет воспоминаний. Были здесь? Поделитесь своей историей.',"zh":'暂无回忆。您来过这里吗？欢迎分享您的故事。'},
'label_33': {"en":'Based on sources and news monitoring. Curators confirm every change of status.',"ru":'Основано на источниках и новостях. Изменения статуса подтверждает куратор.',"zh":'依据资料和新闻，状态变更由策展人确认。'},
'label_34': {"en":'The practices, crafts and people that give this place its meaning.',"ru":'Традиции, ремёсла и люди, которые наполняют это место смыслом.',"zh":'赋予这个地方意义的传统、技艺与人物。'},
'label_35': {"en":'A chronicle of what happened here, with dated photographs from open archives and memories from people.',"ru":'Хроника событий с архивными фотографиями и воспоминаниями.',"zh":'结合档案照片和个人回忆的历史记录。'},
})

COPY.update({'view_3d': {'en': 'Explore in 3D', 'ru': 'Посмотреть в 3D', 'zh': '探索三维视图'}, 'exterior_intro': {'en': 'Explore the exterior and its surroundings using Google’s available imagery. This is not a historical reconstruction; imagery dates and detail vary.', 'ru': 'Рассмотрите внешний вид и окружение по доступным данным Google. Это не историческая реконструкция: дата съёмки и детализация могут различаться.', 'zh': '使用 Google 的可用影像探索建筑外观及周边。此视图并非历史重建，影像日期与细节因地点而异。'}, 'load_3d': {'en': 'Load Google 3D view', 'ru': 'Открыть 3D-вид Google', 'zh': '加载 Google 三维视图'}, 'maps_unconfigured': {'en': 'The 3D view is not connected yet. You can already explore the archive and contribute photographs.', 'ru': '3D-просмотр пока не подключён. История и отправка фотографий уже доступны.', 'zh': '三维视图尚未连接，您仍可浏览档案并提交照片。'}, 'maps_no_coordinates': {'en': 'The location needs to be verified before a 3D view can be opened.', 'ru': 'Чтобы открыть 3D-вид, сначала нужно уточнить координаты места.', 'zh': '打开三维视图前需确认地点坐标。'}, 'maps_loading': {'en': 'Loading the map…', 'ru': 'Загружаем карту…', 'zh': '正在加载地图…'}, 'maps_error': {'en': 'The 3D view could not be loaded. This does not establish whether this building has 3D coverage. Please try again later.', 'ru': 'Не удалось загрузить 3D-вид. Это не означает, что у здания нет покрытия. Попробуйте позже.', 'zh': '三维视图加载失败。这并不意味着该建筑没有三维覆盖，请稍后重试。'}, 'maps_loaded': {'en': 'Map loaded. Building detail and coverage still need to be checked for this location.', 'ru': 'Карта загружена. Покрытие и детализацию конкретного здания ещё нужно проверить.', 'zh': '地图已加载，仍需确认该建筑的覆盖和细节。'}, 'reconstruction_title': {'en': 'Help document the exterior', 'ru': 'Помогите сохранить внешний облик', 'zh': '帮助记录建筑外观'}, 'reconstruction_help': {'en': 'If the map does not show the building or you have photographs of its earlier appearance, share them with the archive. Overlapping views of the front, sides and rear, with dates and sources, can support a future reconstruction. Reconstruction is not yet automated.', 'ru': 'Если карта не показывает здание или у вас есть фотографии его прежнего облика, поделитесь ими с архивом. Для будущей реконструкции нужны перекрывающиеся ракурсы фасада, боковых и задней сторон, даты и источники. Автоматическая реконструкция пока не подключена.', 'zh': '若地图未显示建筑，或您有其旧貌照片，欢迎分享。带有日期和来源的正面、侧面及背面重叠视角可支持未来重建。自动重建尚未启用。'}})


# About and team pages.
COPY.update({'about_nav': {'en': 'About', 'ru': 'О проекте', 'zh': '关于项目'},
 'start': {'en': 'Start exploring', 'ru': 'Начать исследование', 'zh': '开始探索'},
 'about_eyebrow': {'en': 'SMART ARCHIVE FOR VIRTUAL EXPLORATION OF HERITAGE',
                   'ru': 'ЦИФРОВОЙ АРХИВ ДЛЯ ВИРТУАЛЬНОГО ИЗУЧЕНИЯ НАСЛЕДИЯ',
                   'zh': '文化遗产虚拟探索智能档案'},
 'about_title': {'en': 'Places hold memories. Let’s keep them alive.',
                 'ru': 'Места хранят воспоминания. Сохраним их вместе.',
                 'zh': '地方承载记忆。让我们共同留住它们。'},
 'about_intro': {'en': 'SAVE Heritage brings together the stories, photographs and memories of places that '
                       'matter — making cultural heritage easier to explore, share and preserve.',
                 'ru': 'SAVE Heritage объединяет истории, фотографии и воспоминания о значимых местах, чтобы '
                       'культурное наследие было проще изучать, сохранять и передавать другим.',
                 'zh': 'SAVE Heritage 汇集重要场所的故事、照片与个人记忆，让文化遗产更容易被探索、分享和保存。'},
 'about_secondary': {'en': 'Meet the team', 'ru': 'Познакомиться с командой', 'zh': '认识我们的团队'},
 'why_label': {'en': 'WHY WE STARTED', 'ru': 'ПОЧЕМУ МЫ НАЧАЛИ', 'zh': '我们的初衷'},
 'why_title': {'en': 'A place is more than its buildings.',
               'ru': 'Место — это больше, чем его здания.',
               'zh': '一个地方，不只是建筑。'},
 'why_body': {'en': 'Its history lives in family albums, archive records and the memories of people who know '
                    'it. These fragments are often scattered. We started SAVE Heritage to bring them '
                    'together and make them part of a shared digital record.',
              'ru': 'Его история живёт в семейных альбомах, архивных документах и воспоминаниях людей. Часто '
                    'эти материалы разрозненны. Мы создали SAVE Heritage, чтобы собрать их вместе и сделать '
                    'частью общего цифрового архива.',
              'zh': '它的历史存在于家庭相册、档案文献，以及熟悉它的人们的记忆中。这些片段往往散落各处。我们创建 SAVE Heritage，希望将它们汇集起来，成为共同的数字档案。'},
 'how_label': {'en': 'EXPLORE · CONTRIBUTE · PRESERVE',
               'ru': 'ИЗУЧАТЬ · ДЕЛИТЬСЯ · СОХРАНЯТЬ',
               'zh': '探索 · 分享 · 保存'},
 'how_title': {'en': 'Every place has its own story.',
               'ru': 'У каждого места — своя история.',
               'zh': '每个地方，都有自己的故事。'},
 'story_title': {'en': 'Discover a place', 'ru': 'Откройте новое место', 'zh': '发现一个地方'},
 'story_body': {'en': 'Start with a place name or an article link. Explore a short illustrated story, then '
                      'visit its dedicated page for historical context, photographs and sources.',
                'ru': 'Начните с названия места или ссылки на статью. Прочитайте короткую историю с '
                      'иллюстрациями, а затем откройте отдельную страницу с историческим контекстом, '
                      'фотографиями и источниками.',
                'zh': '从地点名称或文章链接开始，阅读简短的图文故事，再进入该地点的专属页面，了解历史背景、照片与资料来源。'},
 'memory_title': {'en': 'Add your memories', 'ru': 'Поделитесь воспоминаниями', 'zh': '分享您的记忆'},
 'memory_body': {'en': 'Share a photograph, a personal memory or new material through a place’s page. '
                       'Contributions are reviewed before publication, helping the archive grow with care.',
                 'ru': 'Добавьте фотографию, личное воспоминание или новые материалы на странице места. '
                       'Перед публикацией материалы проходят проверку — так архив пополняется бережно и '
                       'осмысленно.',
                 'zh': '在地点页面分享照片、个人回忆或新资料。投稿经过审核后才会发布，让档案在审慎整理中不断丰富。'},
 'dim_title': {'en': 'See another dimension', 'ru': 'Посмотрите в новом измерении', 'zh': '从另一个维度了解'},
 'dim_body': {'en': 'Some places include a 3D view where suitable resources are available, offering another '
                    'way to explore their architecture and surroundings.',
              'ru': 'Для некоторых мест доступны 3D-виды на основе имеющихся ресурсов. Они дают ещё один '
                    'способ познакомиться с архитектурой и окружением места.',
              'zh': '部分地点在有合适资源的情况下提供三维视图，让您以另一种方式探索建筑及其周边环境。'},
 'future_label': {'en': 'LOOKING AHEAD', 'ru': 'НАШИ ПЛАНЫ', 'zh': '未来计划'},
 'future_title': {'en': 'More shared memories.\nA\u00a0richer digital future.',
                  'ru': 'Больше воспоминаний. Полнее цифровой образ.',
                  'zh': '更多共同记忆，更丰富的数字未来。'},
 'future_body': {'en': 'As the archive grows, we hope to explore 3D reconstruction and generation grounded '
                       'in richer collections of photographs, documents and other evidence. This is a future '
                       'direction: useful models will depend on the quality of the material, the tools and '
                       'the resources available.',
                 'ru': 'По мере роста архива мы планируем исследовать возможности 3D-реконструкции и '
                       'генерации на основе более полных подборок фотографий, документов и других '
                       'свидетельств. Это направление на будущее: качество моделей будет зависеть от '
                       'собранных материалов, доступных инструментов и ресурсов.',
                 'zh': '随着档案不断丰富，我们希望探索基于更多照片、文献和其他证据的三维重建与生成。这是未来的发展方向：有价值的模型将取决于资料质量，以及可用的工具和资源。'},
 'future_note': {'en': 'Today, every contribution helps build a fuller record of a place.',
                 'ru': 'А уже сегодня каждый вклад помогает полнее сохранить историю места.',
                 'zh': '而在今天，每一份分享都能帮助我们更完整地记录一个地方。'},
 'cta_title': {'en': 'Which place will you discover?', 'ru': 'Какое место вы откроете?', 'zh': '您想探索哪个地方？'},
 'cta_body': {'en': 'Explore its story. Share what you remember. Help preserve what matters.',
              'ru': 'Изучите его историю. Поделитесь воспоминанием. Помогите сохранить важное.',
              'zh': '了解它的故事，分享您的记忆，帮助保存珍贵的文化遗产。'},
 'logo_alt': {'en': 'SAVE Heritage — a classical arch connected by a network of nodes',
              'ru': 'SAVE Heritage — классическая арка, соединённая сетью цифровых связей',
              'zh': 'SAVE Heritage 标志：古典拱门与连接节点组成的网络'},
 'team_team': {'en': 'Team', 'ru': 'Команда', 'zh': '团队'},
 'team_eyebrow': {'en': 'THE PEOPLE BEHIND SAVE HERITAGE',
                  'ru': 'ЛЮДИ, КОТОРЫЕ СОЗДАЮТ SAVE HERITAGE',
                  'zh': 'SAVE HERITAGE 背后的团队'},
 'team_intro': {'en': 'Meet our team', 'ru': 'Наша команда', 'zh': '认识我们的团队'},
 'team_sub': {'en': 'Different disciplines. A shared commitment to preserving heritage.',
              'ru': 'Разные дисциплины. Общее стремление сохранять наследие.',
              'zh': '不同的专业，共同守护文化遗产。'},
 'team_focus': {'en': 'Focus', 'ru': 'Направления', 'zh': '专注领域'},
 'team_support': {'en': 'Supported by House of Scholars',
                  'ru': 'При поддержке House of Scholars',
                  'zh': '由 House of Scholars 支持'},
 'team_description': {'en': 'House of Scholars is a selective leadership development programme under the '
                            'Leadership Qualities Centre at Hong Kong Baptist University. It aims to develop '
                            'high-achieving students into future-shaping leaders who can design and '
                            'implement solutions for global issues and social challenges. Through seed '
                            'funding, tailored consultation, transdisciplinary collaboration, and access to '
                            'university resources and networks, the programme supports students in '
                            'transforming ideas into measurable and impactful projects.',
                      'ru': 'House of Scholars — конкурсная программа развития лидерских качеств Центра '
                            'лидерских качеств Гонконгского баптистского университета. Она помогает '
                            'студентам с высокими достижениями стать лидерами, способными формировать '
                            'будущее: разрабатывать и воплощать решения глобальных проблем и социальных '
                            'вызовов. Благодаря стартовому финансированию, индивидуальным консультациям, '
                            'междисциплинарному сотрудничеству, а также доступу к ресурсам и партнёрским '
                            'связям университета программа помогает студентам превращать идеи в проекты с '
                            'измеримым и значимым результатом.',
                      'zh': 'House of Scholars '
                            '是香港浸会大学领袖素质中心旗下的一项择优录取的领导力发展计划，旨在培养表现优秀的学生成为塑造未来的领袖，设计并实施应对全球问题和社会挑战的解决方案。通过启动资金、个性化咨询、跨学科合作，以及大学资源与合作网络，该计划支持学生将创意转化为成果可衡量且具有实际影响力的项目。'},
 'team_learn': {'en': 'Learn more about House of Scholars',
                'ru': 'Подробнее о House of Scholars',
                'zh': '了解更多关于 House of Scholars'},
 'team_credit': {'en': 'Created by House of Scholars with ♡',
                 'ru': 'Создано House of Scholars с любовью ♡',
                 'zh': '由 House of Scholars 用心打造 ♡'},
 'team_degree_0': {'en': 'Year 3 Business & Computer Science Student',
                   'ru': 'Студент 3-го курса, бизнес и компьютерные науки',
                   'zh': '工商管理与计算机科学专业三年级学生'},
 'team_degree_1': {'en': 'Year 4 Business Administration (Global Entertainment) Student',
                   'ru': 'Студентка 4-го курса, управление бизнесом (глобальная индустрия развлечений)',
                   'zh': '工商管理（环球娱乐）专业四年级学生'},
 'team_degree_2': {'en': 'Year 3 Biotechnology Student',
                   'ru': 'Студентка 3-го курса, биотехнологии',
                   'zh': '生物技术专业三年级学生'},
 'team_focus_0': {'en': 'AI Product Design, Software Development',
                  'ru': 'Дизайн ИИ-продуктов, разработка программного обеспечения',
                  'zh': '人工智能产品设计、软件开发'},
 'team_focus_1': {'en': 'Non-profit and Events Management in Arts and Culture',
                  'ru': 'Управление некоммерческими организациями и мероприятиями в сфере искусства и '
                        'культуры',
                  'zh': '艺术与文化领域的非营利组织及活动管理'},
 'team_focus_2': {'en': 'Biotechnology and Consulting', 'ru': 'Биотехнологии и консалтинг', 'zh': '生物技术与咨询'}})
