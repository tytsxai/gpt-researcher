import { NextResponse } from 'next/server';

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  const { id } = params;
  const backendUrl = process.env.NEXT_PUBLIC_GPTR_API_URL || 'http://localhost:8000';
  const apiKey = process.env.GPTR_API_KEY;
  const authHeaders = apiKey ? { 'X-API-Key': apiKey } : {};
  
  try {
    console.log(`GET /api/reports/${id} - Proxying request to backend`);
    
    const response = await fetch(`${backendUrl}/api/reports/${id}`, {
      headers: authHeaders,
    });
    
    if (!response.ok) {
      // Handle backend errors
      const errorData = await response.json().catch(() => ({ detail: `Error ${response.status}` }));
      return NextResponse.json(
        { error: errorData.detail || 'Failed to fetch report' },
        { status: response.status }
      );
    }
    
    const data = await response.json();
    return NextResponse.json(data, { status: 200 });
  } catch (error) {
    console.error(`GET /api/reports/${id} - Error proxying to backend:`, error);
    return NextResponse.json(
      { error: 'Failed to connect to backend service' },
      { status: 500 }
    );
  }
}

export async function DELETE(
  request: Request,
  { params }: { params: { id: string } }
) {
  const { id } = params;
  const backendUrl = process.env.NEXT_PUBLIC_GPTR_API_URL || 'http://localhost:8000';
  const apiKey = process.env.GPTR_API_KEY;
  const authHeaders = apiKey ? { 'X-API-Key': apiKey } : {};
  
  try {
    console.log(`DELETE /api/reports/${id} - Proxying request to backend`);
    
    const response = await fetch(`${backendUrl}/api/reports/${id}`, {
      method: 'DELETE',
      headers: authHeaders,
    });
    
    if (!response.ok && response.status !== 404) {
      // Handle backend errors
      const errorData = await response.json().catch(() => ({ detail: `Error ${response.status}` }));
      return NextResponse.json(
        { error: errorData.detail || 'Failed to delete report' },
        { status: response.status }
      );
    }
    
    return NextResponse.json({ success: true }, { status: 200 });
  } catch (error) {
    console.error(`DELETE /api/reports/${id} - Error proxying to backend:`, error);
    return NextResponse.json(
      { error: 'Failed to connect to backend service' },
      { status: 500 }
    );
  }
}

export async function PUT(
  request: Request,
  { params }: { params: { id: string } }
) {
  const { id } = params;
  const backendUrl = process.env.NEXT_PUBLIC_GPTR_API_URL || 'http://localhost:8000';
  const apiKey = process.env.GPTR_API_KEY;
  const authHeaders = apiKey ? { 'X-API-Key': apiKey } : {};
  
  try {
    // Parse the request body
    let body;
    try {
      body = await request.json();
    } catch (parseError) {
      console.error('Error parsing request body:', parseError);
      return NextResponse.json(
        { error: 'Invalid JSON in request body' },
        { status: 400 }
      );
    }
    
    console.log(`PUT /api/reports/${id} - Proxying request to backend`);
    
    const response = await fetch(`${backendUrl}/api/reports/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders,
      },
      body: JSON.stringify(body),
    });
    
    if (!response.ok) {
      // Handle backend errors
      const errorData = await response.json().catch(() => ({ detail: `Error ${response.status}` }));
      return NextResponse.json(
        { error: errorData.detail || 'Failed to update report' },
        { status: response.status }
      );
    }
    
    const data = await response.json();
    return NextResponse.json(data, { status: 200 });
  } catch (error) {
    console.error(`PUT /api/reports/${id} - Error proxying to backend:`, error);
    return NextResponse.json(
      { error: 'Failed to connect to backend service' },
      { status: 500 }
    );
  }
} 
