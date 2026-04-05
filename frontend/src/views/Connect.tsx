interface Props {
  onConnect: () => void
  error?: string
}

export default function Connect({ onConnect, error }: Props) {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-950 text-white">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-10 max-w-md w-full text-center shadow-xl">
        <h1 className="text-2xl font-semibold mb-2">Gmail Cleanup Tool</h1>
        <p className="text-gray-400 mb-8">
          Connect your Gmail account to start cleaning up emails.
        </p>
        {error && (
          <p className="text-red-400 text-sm mb-4 bg-red-900/20 border border-red-800 rounded-lg px-4 py-2">
            {error}
          </p>
        )}
        <button
          onClick={onConnect}
          className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-3 px-6 rounded-lg transition-colors"
        >
          Connect Gmail
        </button>
        <p className="text-gray-500 text-xs mt-6">
          Your emails are processed locally. Nothing leaves your machine except requests to Google's API.
        </p>
      </div>
    </div>
  )
}
