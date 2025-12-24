export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">🤖 Telegram AI Bot</h1>
        <p className="text-xl mb-8">
          AI-ассистент с памятью и доступом в интернет
        </p>
        <div className="max-w-2xl mx-auto text-left">
          <h2 className="text-2xl font-semibold mb-4">Возможности:</h2>
          <ul className="list-disc list-inside space-y-2">
            <li>🌐 Поиск информации в интернете</li>
            <li>🤖 Несколько AI моделей на выбор</li>
            <li>💾 Память о предыдущих сообщениях</li>
            <li>💻 Красивое форматирование кода</li>
            <li>📥 Скачивание кода в файлы</li>
            <li>📸 Анализ изображений</li>
            <li>📄 Чтение файлов кода</li>
          </ul>
          <h2 className="text-2xl font-semibold mt-8 mb-4">Команды бота:</h2>
          <ul className="list-disc list-inside space-y-2">
            <li><code>/start</code> - начать работу с ботом</li>
            <li><code>/model</code> - выбрать AI модель</li>
            <li><code>/web</code> - вкл/выкл интернет-поиск</li>
            <li><code>/clear</code> - очистить историю</li>
            <li><code>/history</code> - просмотр истории</li>
            <li><code>/help</code> - справка</li>
          </ul>
        </div>
      </div>
    </main>
  )
}
