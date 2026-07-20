import React, { useEffect, useState } from 'react';
import { CheckCircle, AlertCircle, Loader } from 'lucide-react';
import { getApiUrl } from '../config';

export default function ServiceStatusWidget() {
  const [services, setServices] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const checkServices = async () => {
      try {
        setLoading(true);
        const response = await fetch(`${getApiUrl()}/api/services/status`);
        if (response.ok) {
          const data = await response.json();
          setServices(data);
        } else {
          setError('Could not fetch service status');
        }
      } catch (err) {
        console.error('Error checking services:', err);
        setError('Network error');
      } finally {
        setLoading(false);
      }
    };

    // Check on mount
    checkServices();

    // Check every 5 minutes
    const interval = setInterval(checkServices, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg flex items-center gap-2">
        <Loader size={16} className="animate-spin text-blue-400" />
        <span className="text-xs text-blue-300">Checking service status...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
        <p className="text-xs text-yellow-300">{error}</p>
      </div>
    );
  }

  const allServicesAvailable = Object.values(services).every(s => s.available);

  return (
    <div className={`p-4 rounded-lg border ${
      allServicesAvailable
        ? 'bg-green-500/10 border-green-500/20'
        : 'bg-yellow-500/10 border-yellow-500/20'
    }`}>
      <div className="flex items-center gap-2 mb-3">
        {allServicesAvailable ? (
          <>
            <CheckCircle size={16} className="text-green-400" />
            <p className="text-xs font-medium text-green-300">All services configured</p>
          </>
        ) : (
          <>
            <AlertCircle size={16} className="text-yellow-400" />
            <p className="text-xs font-medium text-yellow-300">Some services need configuration</p>
          </>
        )}
      </div>

      <div className="space-y-2">
        {Object.entries(services).map(([service, status]) => (
          <div key={service} className="flex items-center justify-between text-xs">
            <span className="capitalize text-zinc-400">{service}</span>
            <div className="flex items-center gap-1">
              <div className={`w-2 h-2 rounded-full ${
                status.available ? 'bg-green-400' : 'bg-yellow-400'
              }`} />
              <span className={status.available ? 'text-green-300' : 'text-yellow-300'}>
                {status.available ? 'Ready' : 'Not configured'}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

